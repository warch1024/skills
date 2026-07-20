---
name: dir-tree-generator
version: "1.0"
description: Generate ASCII directory tree structures with .gitignore-aware filtering, file size display, depth control, pattern matching, and multiple output formats (text, JSON, Markdown). Useful for documentation, project structure overviews, and code reviews.
---

# Directory Tree Generator Skill (v1.0)

## Overview

Generate beautiful ASCII directory tree representations. Supports .gitignore-aware filtering, custom depth limits, file size display, pattern-based include/exclude, and multiple output formats.

## Usage

```bash
python scripts/dir_tree.py [directory] [options]
```

### Options

| Flag | Description |
|------|-------------|
| `-d, --depth` | Maximum depth (default: unlimited) |
| `-L, --max-depth` | Same as --depth |
| `-s, --size` | Show file sizes |
| `-S, --sort` | Sort: name/size/time (default: name) |
| `-r, --reverse` | Reverse sort order |
| `-I, --ignore` | Ignore .gitignore rules? (default: respect .gitignore) |
| `-P, --pattern` | Include patterns (glob, repeatable) |
| `-X, --exclude` | Exclude patterns (glob, repeatable) |
| `-f, --format` | Output: text/md/json (default: text) |
| `-o, --output` | Output file |
| `-a, --all` | Show hidden files (dotfiles) |
| `--dirs-only` | Show directories only |

### Examples

```bash
# Basic tree
python scripts/dir_tree.py /path/to/project

# Depth 2, with sizes
python scripts/dir_tree.py ./src -d 2 -s

# Exclude node_modules and .git
python scripts/dir_tree.py . -X "node_modules" -X ".git" -X "__pycache__"

# Markdown output for docs
python scripts/dir_tree.py ./src -f md -o TREE.md

# Include only Python files
python scripts/dir_tree.py . -P "*.py" -P "*.pyi" -P "requirements*.txt"

# JSON output for programmatic use
python scripts/dir_tree.py . -f json -o tree.json
```
