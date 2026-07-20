#!/usr/bin/env python3
"""
Directory Tree Generator — Generate ASCII/JSON/Markdown directory trees
with .gitignore-aware filtering, file sizes, depth control, and patterns.
"""
import argparse
import os
import sys
import json
from pathlib import Path
from fnmatch import fnmatch


def load_gitignore(root):
    """Load .gitignore patterns from root directory and parents."""
    ignores = []
    gitignore_path = os.path.join(root, '.gitignore')
    if os.path.isfile(gitignore_path):
        with open(gitignore_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignores.append(line)
    # always ignore .git
    ignores.append('.git')
    return ignores


def should_ignore(name, patterns):
    for p in patterns:
        if fnmatch(name, p) or fnmatch(name, '*/' + p):
            return True
    return False


def sizeof_fmt(num):
    for unit in ('B', 'K', 'M', 'G', 'T'):
        if abs(num) < 1024.0:
            return f"{num:3.0f}{unit}" if unit == 'B' else f"{num:4.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}P"


def build_tree(root_path, opts):
    """Build a tree data structure."""
    root = Path(root_path).resolve()
    ignore_patterns = load_gitignore(root) if opts.gitignore else []
    if opts.exclude:
        ignore_patterns.extend(opts.exclude)

    def _build(dir_path, depth=0):
        if opts.max_depth is not None and depth > opts.max_depth:
            return None

        entries = []
        try:
            for entry in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                name = entry.name

                # dotfiles
                if name.startswith('.') and not opts.all:
                    continue

                # gitignore
                if opts.gitignore and should_ignore(name, ignore_patterns):
                    continue

                # include patterns
                if opts.patterns:
                    matched = any(fnmatch(name, p) or (entry.is_dir() and fnmatch(name + '/', p))
                                  for p in opts.patterns)
                    if not matched:
                        continue

                # exclude patterns (additional)
                if opts.exclude and should_ignore(name, opts.exclude):
                    continue

                info = {'name': name}

                if entry.is_dir():
                    info['type'] = 'dir'
                    children = _build(entry, depth + 1)
                    if children is not None:
                        info['children'] = children
                    if opts.dirs_only and not info.get('children'):
                        continue
                else:
                    info['type'] = 'file'
                    try:
                        info['size'] = entry.stat().st_size
                    except OSError:
                        info['size'] = 0

                entries.append(info)
        except PermissionError:
            pass

        if opts.sort == 'name':
            entries.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
        elif opts.sort == 'size':
            entries.sort(key=lambda x: (x.get('size', 0) if x['type'] == 'file' else -1))
        elif opts.sort == 'time':
            entries.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))

        if opts.reverse:
            entries.reverse()

        return entries

    tree = _build(root)
    return {'root': str(root), 'children': tree or []}


def render_text(tree, opts, prefix=''):
    """Render tree as ASCII."""
    lines = [tree['root'] + '/']
    children = tree.get('children', [])
    for i, entry in enumerate(children):
        is_last = i == len(children) - 1
        connector = '└── ' if is_last else '├── '
        ext = '    ' if is_last else '│   '

        line = prefix + connector + entry['name']
        if entry['type'] == 'dir':
            line += '/'
        if opts.size and entry['type'] == 'file' and entry.get('size', 0) >= 0:
            line += f"  ({sizeof_fmt(entry['size'])})"

        lines.append(line)

        if 'children' in entry:
            sub = render_text({'root': entry['name'], 'children': entry['children']},
                              opts, prefix + ext)
            lines.extend(sub.splitlines()[1:])

    return '\n'.join(lines)


def render_markdown(tree, opts, depth=0):
    """Render tree as Markdown list."""
    lines = []
    if depth == 0:
        lines.append(f"# Directory Tree: `{tree['root']}`\n")
    children = tree.get('children', [])
    for entry in children:
        indent = '  ' * depth
        bullet = f"{indent}- **{entry['name']}**" if entry['type'] == 'dir' else f"{indent}- {entry['name']}"
        if opts.size and entry['type'] == 'file' and entry.get('size', 0) >= 0:
            bullet += f" ({sizeof_fmt(entry['size'])})"
        if entry['type'] == 'dir':
            bullet += '/'
        lines.append(bullet)
        if 'children' in entry:
            sub = render_markdown({'root': '', 'children': entry['children']},
                                  opts, depth + 1)
            lines.extend(sub)
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Directory Tree Generator')
    parser.add_argument('directory', nargs='?', default='.',
                        help='Directory to scan')
    parser.add_argument('-d', '--depth', type=int, default=None,
                        help='Max depth')
    parser.add_argument('--max-depth', type=int, dest='depth',
                        help='Max depth (alias)')
    parser.add_argument('-s', '--size', action='store_true',
                        help='Show file sizes')
    parser.add_argument('-S', '--sort', choices=['name', 'size', 'time'],
                        default='name', help='Sort order')
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='Reverse sort')
    parser.add_argument('-I', '--no-gitignore', action='store_false',
                        dest='gitignore', help='Ignore .gitignore')
    parser.add_argument('-P', '--pattern', dest='patterns',
                        action='append', default=[],
                        help='Include glob patterns')
    parser.add_argument('-X', '--exclude', dest='exclude',
                        action='append', default=[],
                        help='Exclude glob patterns')
    parser.add_argument('-f', '--format', choices=['text', 'md', 'json'],
                        default='text', help='Output format')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-a', '--all', action='store_true',
                        help='Show hidden files')
    parser.add_argument('--dirs-only', action='store_true',
                        help='Directories only')
    parser.set_defaults(gitignore=True)

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    tree = build_tree(args.directory, args)

    if args.format == 'json':
        output = json.dumps(tree, indent=2, ensure_ascii=False)
    elif args.format == 'md':
        output = render_markdown(tree, args)
    else:
        output = render_text(tree, args)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output + '\n')
        print(f"Tree written to {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
