#!/usr/bin/env python3
"""
Env File Manager — Manage .env files: diff, merge, validate,
encrypt/decrypt, sort, check, and generate .env.example.
"""
import argparse
import sys
import os
import json
import re
from base64 import b64encode, b64decode
from hashlib import pbkdf2_hmac


# ---------- .env parsing / writing ----------

def parse_env(text):
    """Parse .env text into list of (key, value, comment_before, inline_comment) tuples."""
    lines = text.splitlines()
    entries = []
    comment_buf = []
    for line in lines:
        stripped = line.strip()
        if stripped == '':
            comment_buf.append(line)
            continue
        if stripped.startswith('#'):
            comment_buf.append(line)
            continue
        # key=value line (possibly with inline comment)
        inline_comment = None
        val_part = stripped
        # check for inline comment (outside quoted value)
        in_quote = False
        for i, ch in enumerate(val_part):
            if ch == '"' and (i == 0 or val_part[i-1] != '\\'):
                in_quote = not in_quote
            if ch == '#' and not in_quote:
                inline_comment = val_part[i:].strip()
                val_part = val_part[:i].strip()
                break
        if '=' not in val_part:
            comment_buf.append(line)
            continue
        key, _, value = val_part.partition('=')
        entries.append({
            'key': key.strip(),
            'value': value.strip(),
            'comments': comment_buf[:],
            'inline_comment': inline_comment,
        })
        comment_buf = []
    if comment_buf:
        entries.append({'key': None, 'value': None,
                        'comments': comment_buf, 'inline_comment': None})
    return entries


def format_env(entries):
    """Format entries back to .env text."""
    lines = []
    for e in entries:
        for c in e.get('comments', []):
            lines.append(c)
        if e['key'] is not None:
            line = f"{e['key']}={e['value']}"
            if e.get('inline_comment'):
                line += f"  {e['inline_comment']}"
            lines.append(line)
    return '\n'.join(lines)


def read_env(path):
    with open(path, 'r', encoding='utf-8') as f:
        return parse_env(f.read())


def write_env(path, entries):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(format_env(entries))
        f.write('\n')


def entries_to_dict(entries):
    return {e['key']: e['value'] for e in entries if e['key']}


# ---------- encryption (simple XOR with PBKDF2 key) ----------

def _derive_key(password: str, salt: bytes) -> bytes:
    return pbkdf2_hmac('sha256', password.encode(), salt, 100000, 32)


def encrypt_value(value: str, password: str) -> str:
    if not value:
        return value
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    data = value.encode()
    encrypted = bytes(a ^ b for a, b in zip(data, key[:len(data)]))
    return f"enc:{b64encode(salt + encrypted).decode()}"


def decrypt_value(value: str, password: str) -> str:
    if not value.startswith('enc:'):
        return value
    raw = b64decode(value[4:])
    salt, data = raw[:16], raw[16:]
    key = _derive_key(password, salt)
    decrypted = bytes(a ^ b for a, b in zip(data, key[:len(data)]))
    return decrypted.decode()


# ---------- commands ----------

def cmd_diff(args):
    e1 = read_env(args.file1)
    e2 = read_env(args.file2)
    d1 = entries_to_dict(e1)
    d2 = entries_to_dict(e2)
    all_keys = sorted(set(d1.keys()) | set(d2.keys()))
    if not all_keys:
        print("No differences (both files empty or no keys)")
        return
    changes = []
    for k in all_keys:
        v1 = d1.get(k, '<MISSING>')
        v2 = d2.get(k, '<MISSING>')
        if v1 != v2:
            changes.append((k, v1, v2))
    if not changes:
        print("Files are identical.")
        return
    for k, v1, v2 in changes:
        if args.show_values:
            print(f"  {k}: {v1}  →  {v2}")
        else:
            status = []
            if v1 == '<MISSING>':
                status.append('added')
            elif v2 == '<MISSING>':
                status.append('removed')
            else:
                status.append('changed')
            print(f"  [{', '.join(status)}] {k}")


def cmd_merge(args):
    base = read_env(args.file) if args.file else []
    overrides = []
    for f in args.files:
        overrides.extend(read_env(f))
    merged = {e['key']: e for e in base if e['key']}
    for e in overrides:
        if e['key']:
            merged[e['key']] = e
    entries = list(merged.values())
    if args.output:
        write_env(args.output, entries)
        print(f"Merged into {args.output}")
    else:
        print(format_env(entries))


def cmd_validate(args):
    entries = read_env(args.file)
    if args.schema:
        with open(args.schema) as f:
            schema = json.load(f)
        required = schema.get('required', [])
        patterns = schema.get('patterns', {})
        errors = []
        env_dict = entries_to_dict(entries)
        for r in required:
            if r not in env_dict:
                errors.append(f"Missing required key: {r}")
        for key, pat in patterns.items():
            if key in env_dict and not re.match(pat, env_dict[key]):
                errors.append(f"Pattern mismatch for {key}: expected {pat}")
        if errors:
            for e in errors:
                print(f"  ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        print("Validation passed.")
    else:
        print(f"Parsed {len([e for e in entries if e['key']])} keys.")


def cmd_encrypt(args):
    entries = read_env(args.file)
    key = args.key or os.environ.get('ENV_MANAGER_KEY', '')
    if not key:
        print("Error: encryption key required (--key or ENV_MANAGER_KEY)", file=sys.stderr)
        sys.exit(1)
    for e in entries:
        if e['key'] and (e['key'].endswith('_SECRET') or e['key'].endswith('_PASSWORD')
                         or e['key'].endswith('_TOKEN') or e['key'].endswith('_KEY')):
            if e['value'] and not e['value'].startswith('enc:'):
                e['value'] = encrypt_value(e['value'], key)
    out = args.output or args.file
    write_env(out, entries)
    print(f"Encrypted → {out}")


def cmd_decrypt(args):
    entries = read_env(args.file)
    key = args.key or os.environ.get('ENV_MANAGER_KEY', '')
    if not key:
        print("Error: decryption key required", file=sys.stderr)
        sys.exit(1)
    for e in entries:
        if e['value'] and e['value'].startswith('enc:'):
            e['value'] = decrypt_value(e['value'], key)
    out = args.output or args.file
    write_env(out, entries)
    print(f"Decrypted → {out}")


def cmd_example(args):
    entries = read_env(args.file)
    example = []
    for e in entries:
        if e['key']:
            example.append({
                'key': e['key'],
                'value': '',
                'comments': e.get('comments', []),
                'inline_comment': e.get('inline_comment'),
            })
        else:
            example.append(e)
    out = args.output or args.file + '.example'
    write_env(out, example)
    print(f"Example written to {out}")


def cmd_check(args):
    main_entries = read_env(args.main)
    ref_entries = read_env(args.reference)
    main_keys = {e['key'] for e in main_entries if e['key']}
    ref_keys = {e['key'] for e in ref_entries if e['key']}
    missing = ref_keys - main_keys
    extra = main_keys - ref_keys
    if missing:
        print(f"Missing keys (in reference but not in file):")
        for k in sorted(missing):
            print(f"  - {k}")
    if extra:
        print(f"Extra keys (in file but not in reference):")
        for k in sorted(extra):
            print(f"  + {k}")
    if not missing and not extra:
        print("All keys match.")


def cmd_sort(args):
    entries = read_env(args.file)
    key_entries = [e for e in entries if e['key']]
    other_entries = [e for e in entries if not e['key']]
    key_entries.sort(key=lambda e: e['key'].lower())
    sorted_entries = other_entries + key_entries
    out = args.output or args.file
    write_env(out, sorted_entries)
    print(f"Sorted → {out}")


def main():
    parser = argparse.ArgumentParser(description='Env File Manager')
    sub = parser.add_subparsers(dest='command', required=True)

    p_diff = sub.add_parser('diff', help='Diff two .env files')
    p_diff.add_argument('file1', help='First .env file')
    p_diff.add_argument('file2', help='Second .env file')
    p_diff.add_argument('--show-values', action='store_true')
    p_diff.set_defaults(func=cmd_diff)

    p_merge = sub.add_parser('merge', help='Merge .env files')
    p_merge.add_argument('-f', '--file', help='Base .env file')
    p_merge.add_argument('files', nargs='+', help='Files to merge in')
    p_merge.add_argument('-o', '--output', help='Output file')
    p_merge.set_defaults(func=cmd_merge)

    p_val = sub.add_parser('validate', help='Validate .env file')
    p_val.add_argument('-f', '--file', required=True)
    p_val.add_argument('-s', '--schema', help='JSON schema')
    p_val.set_defaults(func=cmd_validate)

    p_enc = sub.add_parser('encrypt', help='Encrypt secrets in .env')
    p_enc.add_argument('file')
    p_enc.add_argument('--key')
    p_enc.add_argument('-o', '--output')
    p_enc.set_defaults(func=cmd_encrypt)

    p_dec = sub.add_parser('decrypt', help='Decrypt .env')
    p_dec.add_argument('file')
    p_dec.add_argument('--key')
    p_dec.add_argument('-o', '--output')
    p_dec.set_defaults(func=cmd_decrypt)

    p_ex = sub.add_parser('example', help='Generate .env.example')
    p_ex.add_argument('file')
    p_ex.add_argument('-o', '--output')
    p_ex.set_defaults(func=cmd_example)

    p_ch = sub.add_parser('check', help='Check keys vs reference')
    p_ch.add_argument('main', help='Main .env file')
    p_ch.add_argument('reference', help='Reference .env.example')
    p_ch.set_defaults(func=cmd_check)

    p_sort = sub.add_parser('sort', help='Sort .env keys')
    p_sort.add_argument('file')
    p_sort.add_argument('-o', '--output')
    p_sort.set_defaults(func=cmd_sort)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
