---
name: ip-utils
version: "1.0"
description: IP address and CIDR utility toolkit — CIDR calculations (network address, broadcast, usable hosts), subnet expansion, IP range lookup, subnet mask conversion, IPv4/IPv6 validation, and bulk IP processing.
---

# IP Utils Skill (v1.0)

## Overview

Comprehensive IP address toolkit for network engineers and developers. Supports CIDR calculations, subnet expansion, IP range operations, subnet mask conversion, and bulk IP processing.

## Usage

```bash
python scripts/ip_utils.py <command> [args] [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `cidr` | Calculate CIDR details (network, broadcast, hosts, netmask) |
| `expand` | Expand a CIDR into individual IP addresses |
| `range` | Convert IP range to CIDR(s) or list IPs in range |
| `mask` | Convert between subnet mask notations (dotted, CIDR, binary) |
| `validate` | Validate IP address or CIDR notation |
| `classify` | Classify IP (private/public/loopback/multicast/link-local) |
| `batch` | Process multiple IPs from a file |
| `info` | Show detailed information about an IP |

### Options

| Flag | Description |
|------|-------------|
| `-o, --output` | Output file (default: stdout) |
| `-f, --format` | Output format: text/json/csv (default: text) |
| `--ipv6` | Explicitly treat as IPv6 |

### Examples

```bash
# CIDR calculation
python scripts/ip_utils.py cidr 192.168.1.0/24

# Expand subnet
python scripts/ip_utils.py expand 10.0.0.0/28 --limit 20

# IP range to CIDR
python scripts/ip_utils.py range 192.168.1.0 192.168.1.255

# Mask conversion
python scripts/ip_utils.py mask 255.255.255.0
python scripts/ip_utils.py mask 24

# Validate
python scripts/ip_utils.py validate 192.168.1.1
python scripts/ip_utils.py validate 10.0.0.0/8

# Classify IP
python scripts/ip_utils.py classify 127.0.0.1
python scripts/ip_utils.py classify 192.168.1.1
python scripts/ip_utils.py classify 8.8.8.8

# Batch process
python scripts/ip_utils.py batch ips.txt -f json

# Detailed IP info
python scripts/ip_utils.py info 192.168.1.1
```
