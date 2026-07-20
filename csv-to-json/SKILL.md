---
name: csv-to-json
version: "1.0"
description: Convert CSV files to JSON format with advanced features — type inference, field mapping, key casing, pretty-print, streaming for large files, and schema validation.
---

# CSV to JSON Skill (v1.0)

## Overview

Convert CSV files to structured JSON with intelligent type inference, field mapping, and schema validation. Handles large files via streaming, auto-detects delimiters, and supports nested JSON structures.

## Usage

```bash
python scripts/csv_to_json.py <input.csv> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `-o, --output` | Output JSON file (default: stdout) |
| `-d, --delimiter` | CSV delimiter (default: auto-detect) |
| `-p, --pretty` | Pretty-print JSON output |
| `--key-case` | Key casing: snake/camel/pascal/as-is (default: as-is) |
| `--type-infer` | Auto-infer numeric/boolean types |
| `--schema` | JSON schema file for validation |
| `--flatten` | Flatten nested headers (e.g., "addr.city") |
| `--encoding` | File encoding (default: utf-8) |
| `--max-rows` | Maximum rows to process (0 = all) |
| `--null-value` | String to treat as null (default: empty) |

### Examples

```bash
# Basic conversion
python scripts/csv_to_json.py data.csv

# Pretty-print with type inference
python scripts/csv_to_json.py data.csv -p --type-infer

# Camel case keys, custom delimiter
python scripts/csv_to_json.py data.tsv -d "`t" --key-case camel

# Flatten nested headers
python scripts/csv_to_json.py data.csv --flatten -p

# Validate against schema
python scripts/csv_to_json.py data.csv --schema schema.json -o output.json
```
