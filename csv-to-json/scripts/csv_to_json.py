#!/usr/bin/env python3
"""
CSV to JSON Converter — Convert CSV files to JSON with type inference,
field mapping, key casing, and schema validation.
"""
import argparse
import json
import csv
import sys
import os
import re


def detect_delimiter(path):
    with open(path, 'r', encoding='utf-8') as f:
        sample = f.read(4096)
    delimiters = [',', '\t', ';', '|', ':']
    counts = []
    for d in delimiters:
        n = sample.count(d)
        if n > 0:
            counts.append((d, n))
    counts.sort(key=lambda x: -x[1])
    if counts:
        first_line = sample.split('\n')[0]
        for d, _ in counts:
            if d in first_line:
                return d
    return ','


def to_snake(s):
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return re.sub(r'[^a-zA-Z0-9]', '_', s).lower().strip('_')


def to_camel(s):
    parts = re.split(r'[^a-zA-Z0-9]', s)
    return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])


def to_pascal(s):
    parts = re.split(r'[^a-zA-Z0-9]', s)
    return ''.join(p.capitalize() for p in parts)


def convert_key(key, case):
    if case == 'snake':
        return to_snake(key)
    elif case == 'camel':
        return to_camel(key)
    elif case == 'pascal':
        return to_pascal(key)
    return key


def infer_type(val):
    if val == '' or val is None:
        return None
    v = val.strip()
    if v.lower() in ('true', 'false', 'yes', 'no', 'on', 'off'):
        return v.lower() in ('true', 'yes', 'on')
    try:
        if '.' in v:
            return float(v)
        return int(v)
    except ValueError:
        pass
    return v


def parse_nested_key(key, flatten=True):
    if flatten:
        parts = re.split(r'[.\[\]]+', key)
        return [p for p in parts if p]
    return [key]


def set_nested(d, keys, value):
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def main():
    parser = argparse.ArgumentParser(description='Convert CSV to JSON')
    parser.add_argument('input', help='Input CSV file')
    parser.add_argument('-o', '--output', help='Output JSON file')
    parser.add_argument('-d', '--delimiter', help='CSV delimiter (default: auto-detect)')
    parser.add_argument('-p', '--pretty', action='store_true', help='Pretty-print JSON')
    parser.add_argument('--key-case', choices=['snake', 'camel', 'pascal', 'as-is'],
                        default='as-is', help='Key casing')
    parser.add_argument('--type-infer', action='store_true',
                        help='Auto-infer numeric/boolean types')
    parser.add_argument('--schema', help='JSON schema file for validation')
    parser.add_argument('--flatten', action='store_true',
                        help='Flatten nested headers (e.g., addr.city)')
    parser.add_argument('--encoding', default='utf-8', help='File encoding')
    parser.add_argument('--max-rows', type=int, default=0,
                        help='Maximum rows (0 = all)')
    parser.add_argument('--null-value', default='', help='String to treat as null')

    args = parser.parse_args()

    delim = args.delimiter or detect_delimiter(args.input)
    if delim == '`t':
        delim = '\t'

    schema = None
    if args.schema:
        with open(args.schema, 'r', encoding='utf-8') as f:
            schema = json.load(f)

    rows = []
    with open(args.input, 'r', encoding=args.encoding) as f:
        reader = csv.DictReader(f, delimiter=delim)
        headers = reader.fieldnames
        for i, row in enumerate(reader):
            if args.max_rows > 0 and i >= args.max_rows:
                break
            processed = {}
            for key, val in row.items():
                if not key:
                    continue
                if val == args.null_value:
                    val = None
                elif args.type_infer and val is not None:
                    val = infer_type(val)
                new_key = convert_key(key.strip(), args.key_case)
                if args.flatten:
                    keys = parse_nested_key(key, flatten=True)
                    set_nested(processed, keys, val)
                else:
                    processed[new_key] = val
            rows.append(processed)

    if schema:
        from jsonschema import validate as js_validate
        for i, row in enumerate(rows):
            try:
                js_validate(instance=row, schema=schema)
            except Exception as e:
                print(f"Row {i+1} validation error: {e}", file=sys.stderr)
                sys.exit(1)

    indent = 2 if args.pretty else None
    output = json.dumps(rows, indent=indent, ensure_ascii=False,
                        default=str)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output + '\n')
        print(f"Converted {len(rows)} rows to {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
