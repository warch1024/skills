---
name: hash-verifier
version: "1.0"
description: Compute and verify file integrity hashes (MD5, SHA1, SHA256, SHA512, BLAKE2b). Supports single file hashing, recursive directory scanning, checksum file generation/verification, and multiple output formats (text, JSON, CSV).
---

# Hash Verifier Skill (v1.0)

## Overview

Compute, verify, and manage file integrity hashes. Supports MD5, SHA1, SHA256, SHA512, and BLAKE2b algorithms. Can process single files or entire directory trees, generate checksum files, and verify against existing checksums.

## Usage

```bash
python scripts/hash_verify.py <file_or_dir> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `-a, --algo` | Hash algorithm: md5/sha1/sha256/sha512/blake2b (default: sha256) |
| `-r, --recursive` | Recursively scan directories |
| `-o, --output` | Output file (default: stdout) |
| `-f, --format` | Output format: text/json/csv (default: text) |
| `-c, --check` | Verify against a checksum file |
| `-g, --generate` | Generate checksum file (.md5/.sha1/.sha256 etc.) |
| `-e, --exclude` | Glob patterns to exclude (repeatable) |

### Examples

```bash
# Compute SHA256 of a file
python scripts/hash_verify.py myfile.bin

# Compute MD5 hash only
python scripts/hash_verify.py myfile.bin -a md5

# Recursive with JSON output
python scripts/hash_verify.py ./src -r -f json -o hashes.json

# Generate SHA256 checksum file
python scripts/hash_verify.py ./dist -r -g

# Verify against a checksum file
python scripts/hash_verify.py ./dist -c SHA256SUMS
```
