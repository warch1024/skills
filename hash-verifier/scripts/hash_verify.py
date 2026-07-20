#!/usr/bin/env python3
"""
Hash Verifier — Compute and verify file integrity hashes.
Supports MD5, SHA1, SHA256, SHA512, BLAKE2b.
"""
import hashlib
import argparse
import os
import sys
import json
import csv
import io
from pathlib import Path
from glob import iglob

ALGOS = {
    'md5': hashlib.md5,
    'sha1': hashlib.sha1,
    'sha256': hashlib.sha256,
    'sha512': hashlib.sha512,
    'blake2b': hashlib.blake2b,
}


def compute_file_hash(path: str, algo: str) -> str:
    h = ALGOS[algo]()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def collect_files(paths, recursive=False, exclude=None):
    files = []
    exclude = exclude or []
    for p in paths:
        pobj = Path(p)
        if pobj.is_file():
            files.append(str(pobj.resolve()))
        elif pobj.is_dir():
            if recursive:
                for root, dirs, fnames in os.walk(str(pobj)):
                    for fn in fnames:
                        fp = os.path.join(root, fn)
                        if not any(Path(fp).match(pat) for pat in exclude):
                            files.append(fp)
            else:
                for f in pobj.iterdir():
                    if f.is_file():
                        fp = str(f.resolve())
                        if not any(f.match(pat) for pat in exclude):
                            files.append(fp)
    return sorted(set(files))


def format_text(results):
    lines = []
    for r in results:
        lines.append(f"{r['algo'].upper()}({r['file']}) = {r['hash']}")
    return '\n'.join(lines)


def format_json(results):
    return json.dumps(results, indent=2, ensure_ascii=False)


def format_csv(results):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['algorithm', 'file', 'hash'])
    for r in results:
        w.writerow([r['algo'], r['file'], r['hash']])
    return buf.getvalue().strip()


def generate_checksum_file(results, algo):
    ext = algo.upper() + 'SUMS' if algo != 'blake2b' else 'BLAKE2bSUMS'
    lines = []
    for r in results:
        lines.append(f"{r['hash']}  {r['file']}")
    return ext, '\n'.join(lines) + '\n'


def parse_checksum_file(path):
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                entries.append((parts[0], parts[1].lstrip('*').lstrip() ))
    return entries


def main():
    parser = argparse.ArgumentParser(
        description='Compute and verify file integrity hashes')
    parser.add_argument('paths', nargs='+', help='Files or directories')
    parser.add_argument('-a', '--algo', default='sha256',
                        choices=list(ALGOS.keys()), help='Hash algorithm')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='Recursively scan directories')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-f', '--format', choices=['text', 'json', 'csv'],
                        default='text', help='Output format')
    parser.add_argument('-c', '--check', metavar='CHECKSUM_FILE',
                        help='Verify against a checksum file')
    parser.add_argument('-g', '--generate', action='store_true',
                        help='Generate checksum file')
    parser.add_argument('-e', '--exclude', action='append', default=[],
                        help='Glob patterns to exclude')

    args = parser.parse_args()

    if args.check:
        entries = parse_checksum_file(args.check)
        if not entries:
            print('No entries found in checksum file.', file=sys.stderr)
            sys.exit(1)
        ok = True
        for expected_hash, fpath in entries:
            if not os.path.exists(fpath):
                print(f"FAILED: {fpath} — file not found")
                ok = False
                continue
            try:
                # try to detect algo from hash length
                hlen = len(expected_hash)
                algo_map = {32: 'md5', 40: 'sha1', 56: 'sha224',
                            64: 'sha256', 96: 'sha384', 128: 'sha512'}
                algo = algo_map.get(hlen)
                if not algo:
                    algo = args.algo
                actual = compute_file_hash(fpath, algo)
                if actual == expected_hash:
                    print(f"OK: {fpath}")
                else:
                    print(f"FAILED: {fpath}")
                    print(f"  Expected: {expected_hash}")
                    print(f"  Actual:   {actual}")
                    ok = False
            except Exception as e:
                print(f"FAILED: {fpath} — {e}", file=sys.stderr)
                ok = False
        sys.exit(0 if ok else 1)

    files = collect_files(args.paths, args.recursive, args.exclude)
    if not files:
        print('No files found.', file=sys.stderr)
        sys.exit(1)

    results = []
    for f in files:
        try:
            h = compute_file_hash(f, args.algo)
            results.append({'algo': args.algo, 'file': f, 'hash': h})
        except Exception as e:
            print(f"Error processing {f}: {e}", file=sys.stderr)

    if args.generate:
        ext, content = generate_checksum_file(results, args.algo)
        out_path = args.output or ext
        with open(out_path, 'w') as f:
            f.write(content)
        print(f"Generated {out_path}")
        return

    if args.format == 'json':
        output = format_json(results)
    elif args.format == 'csv':
        output = format_csv(results)
    else:
        output = format_text(results)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output + '\n')
    else:
        print(output)


if __name__ == '__main__':
    main()
