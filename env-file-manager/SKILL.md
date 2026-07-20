---
name: env-file-manager
version: "1.0"
description: Manage .env files across environments — diff, merge, validate, encrypt/decrypt sensitive values, check for missing keys, and generate .env.example files from templates.
---

# Env File Manager Skill (v1.0)

## Overview

Manage environment configuration files (.env, .env.*) across different environments (development, staging, production). Provides diff, merge, validation, and encryption of sensitive values.

## Usage

```bash
python scripts/env_manager.py <command> [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `diff` | Show differences between two .env files |
| `merge` | Merge multiple .env files |
| `validate` | Validate .env structure against a schema |
| `encrypt` | Encrypt sensitive values in .env |
| `decrypt` | Decrypt encrypted .env values |
| `example` | Generate .env.example from .env |
| `check` | Check for missing/extra keys vs .env.example |
| `sort` | Sort keys alphabetically |

### Options

| Flag | Description |
|------|-------------|
| `-f, --file` | Target .env file |
| `-e, --env` | Environment name: dev/staging/prod |
| `-s, --schema` | Schema file for validation |
| `--key` | Encryption/decryption key |
| `--show-values` | Show values in diff output |
| `--no-comments` | Strip comments from output |
| `-o, --output` | Output file |

### Examples

```bash
# Diff two env files
python scripts/env_manager.py diff .env.dev .env.prod

# Validate against schema
python scripts/env_manager.py validate -f .env -s schema.json

# Encrypt secret values (marked with _SECRET suffix)
python scripts/env_manager.py encrypt .env --key mykey

# Generate .env.example (keep keys, blank values, keep comments)
python scripts/env_manager.py example .env -o .env.example

# Check missing keys
python scripts/env_manager.py check .env .env.example

# Sort env file
python scripts/env_manager.py sort .env -o .env.sorted
```
