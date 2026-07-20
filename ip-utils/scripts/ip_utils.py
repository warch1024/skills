#!/usr/bin/env python3
"""
IP Utils — IP address and CIDR utility toolkit.
CIDR calculation, subnet expansion, IP range operations,
mask conversion, validation, classification.
"""
import argparse
import sys
import json
import csv
import io
import ipaddress


def cmd_cidr(args):
    try:
        net = ipaddress.ip_network(args.cidr, strict=False)
    except ValueError as e:
        print(f"Invalid CIDR: {e}", file=sys.stderr)
        sys.exit(1)

    info = {
        'network': str(net.network_address),
        'broadcast': str(net.broadcast_address),
        'netmask': str(net.netmask),
        'cidr': str(net),
        'prefixlen': net.prefixlen,
        'num_addresses': net.num_addresses,
        'num_hosts': max(0, net.num_addresses - 2),
        'first_host': str(list(net.hosts())[0]) if net.num_addresses > 2 else 'N/A',
        'last_host': str(list(net.hosts())[-1]) if net.num_addresses > 2 else 'N/A',
        'is_private': net.is_private,
        'version': net.version,
    }

    if args.format == 'json':
        print(json.dumps(info, indent=2))
    elif args.format == 'csv':
        w = csv.writer(sys.stdout)
        w.writerow(info.keys())
        w.writerow(info.values())
    else:
        print(f"CIDR:         {info['cidr']}")
        print(f"Network:      {info['network']}")
        print(f"Broadcast:    {info['broadcast']}")
        print(f"Netmask:      {info['netmask']}")
        print(f"Prefix:       /{info['prefixlen']}")
        print(f"Addresses:    {info['num_addresses']}")
        print(f"Usable hosts: {info['num_hosts']}")
        print(f"First host:   {info['first_host']}")
        print(f"Last host:    {info['last_host']}")
        print(f"Private:      {info['is_private']}")
        print(f"Version:      IPv{info['version']}")


def cmd_expand(args):
    try:
        net = ipaddress.ip_network(args.cidr, strict=False)
    except ValueError as e:
        print(f"Invalid CIDR: {e}", file=sys.stderr)
        sys.exit(1)

    count = 0
    limit = args.limit or net.num_addresses
    results = []
    for ip in net:
        if count >= limit:
            break
        results.append(str(ip))
        count += 1

    if args.format == 'json':
        print(json.dumps(results, indent=2))
    elif args.format == 'csv':
        w = csv.writer(sys.stdout)
        w.writerow(['ip'])
        for ip in results:
            w.writerow([ip])
    else:
        for ip in results:
            print(ip)
    if limit < net.num_addresses:
        remaining = net.num_addresses - count
        print(f"\n... and {remaining} more addresses (use --limit 0 for all)",
              file=sys.stderr)


def cmd_range(args):
    try:
        start = ipaddress.ip_address(args.start)
        end = ipaddress.ip_address(args.end)
    except ValueError as e:
        print(f"Invalid IP: {e}", file=sys.stderr)
        sys.exit(1)

    if start > end:
        start, end = end, start

    # Try to summarize into CIDRs
    try:
        addr_range = ipaddress.summarize_address_range(start, end)
        cidrs = [str(n) for n in addr_range]
    except (TypeError, ValueError):
        cidrs = []

    if args.format == 'json':
        print(json.dumps({
            'start': str(start),
            'end': str(end),
            'cidrs': cidrs,
        }, indent=2))
    elif args.format == 'csv':
        w = csv.writer(sys.stdout)
        w.writerow(['start', 'end', 'cidrs'])
        w.writerow([str(start), str(end), ' '.join(cidrs)])
    else:
        for c in cidrs:
            print(c)


def cmd_mask(args):
    v = args.value
    # Try CIDR prefix
    if v.isdigit():
        prefix = int(v)
        if 0 <= prefix <= 32:
            mask_int = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
            dotted = f"{(mask_int >> 24) & 0xFF}.{(mask_int >> 16) & 0xFF}.{(mask_int >> 8) & 0xFF}.{mask_int & 0xFF}"
            binary = '.'.join(f"{b:08b}" for b in mask_int.to_bytes(4, 'big'))
            output = {
                'prefix': f"/{prefix}",
                'dotted': dotted,
                'binary': binary,
                'hex': hex(mask_int),
            }
        elif 0 <= prefix <= 128:
            # IPv6
            mask_int = (1 << prefix) - 1 if prefix > 0 else 0
            output = {
                'prefix': f"/{prefix}",
                'hex': hex(mask_int),
                'bits': prefix,
            }
        else:
            print(f"Invalid prefix length: {v}", file=sys.stderr)
            sys.exit(1)
    else:
        # Try dotted decimal
        try:
            parts = [int(x) for x in v.split('.')]
            if len(parts) == 4 and all(0 <= p <= 255 for p in parts):
                mask_int = sum(p << (24 - 8 * i) for i, p in enumerate(parts))
                prefix = bin(mask_int).count('1')
                binary = '.'.join(f"{p:08b}" for p in parts)
                output = {
                    'prefix': f"/{prefix}",
                    'dotted': v,
                    'binary': binary,
                    'hex': hex(mask_int),
                }
            else:
                raise ValueError
        except (ValueError, TypeError):
            print(f"Invalid mask: {v}", file=sys.stderr)
            sys.exit(1)

    if args.format == 'json':
        print(json.dumps(output, indent=2))
    elif args.format == 'csv':
        w = csv.writer(sys.stdout)
        w.writerow(output.keys())
        w.writerow(output.values())
    else:
        if 'dotted' in output:
            format_str = f"Dotted:  {output['dotted']}\n"
        else:
            format_str = ""
        format_str += f"Prefix:  {output['prefix']}\nBinary:  {output['binary']}"
        if 'hex' in output:
            format_str += f"\nHex:     {output['hex']}"
        print(format_str)


def cmd_validate(args):
    v = args.ip
    is_cidr = '/' in v
    try:
        if is_cidr:
            obj = ipaddress.ip_network(v, strict=False)
            r = {'valid': True, 'type': 'network', 'version': f"IPv{obj.version}"}
        else:
            obj = ipaddress.ip_address(v)
            r = {'valid': True, 'type': 'address', 'version': f"IPv{obj.version}"}
    except ValueError as e:
        r = {'valid': False, 'error': str(e)}

    if args.format == 'json':
        print(json.dumps(r, indent=2))
    else:
        if r['valid']:
            print(f"{v} — valid {r['version']} {r['type']}")
        else:
            print(f"{v} — INVALID ({r['error']})")


def cmd_classify(args):
    try:
        ip = ipaddress.ip_address(args.ip)
    except ValueError as e:
        print(f"Invalid IP: {e}", file=sys.stderr)
        sys.exit(1)

    cats = []
    if ip.is_private:
        cats.append('private')
    if ip.is_loopback:
        cats.append('loopback')
    if ip.is_multicast:
        cats.append('multicast')
    if ip.is_link_local:
        cats.append('link-local')
    if ip.is_reserved:
        cats.append('reserved')
    if ip.is_global and not any([ip.is_private, ip.is_loopback,
                                  ip.is_multicast, ip.is_link_local]):
        cats.append('public')
    if ip.is_unspecified:
        cats.append('unspecified')

    result = {
        'ip': str(ip),
        'version': f"IPv{ip.version}",
        'classification': cats or ['unknown'],
    }

    if args.format == 'json':
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['ip']} ({result['version']}): {', '.join(result['classification'])}")


def cmd_batch(args):
    results = []
    with open(args.file) as f:
        for line in f:
            ip_str = line.strip()
            if not ip_str:
                continue
            entry = {'input': ip_str}
            try:
                if '/' in ip_str:
                    obj = ipaddress.ip_network(ip_str, strict=False)
                    entry['valid'] = True
                    entry['version'] = f"IPv{obj.version}"
                    entry['type'] = 'network'
                    entry['network'] = str(obj.network_address)
                    entry['broadcast'] = str(obj.broadcast_address)
                else:
                    obj = ipaddress.ip_address(ip_str)
                    entry['valid'] = True
                    entry['version'] = f"IPv{obj.version}"
                    entry['type'] = 'address'
            except ValueError as e:
                entry['valid'] = False
                entry['error'] = str(e)
            results.append(entry)

    if args.format == 'json':
        print(json.dumps(results, indent=2))
    elif args.format == 'csv':
        if results:
            w = csv.DictWriter(sys.stdout, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
    else:
        for r in results:
            if r['valid']:
                print(f"{r['input']} — valid {r['version']} {r['type']}")
            else:
                print(f"{r['input']} — invalid")


def cmd_info(args):
    try:
        ip = ipaddress.ip_address(args.ip)
    except ValueError:
        try:
            net = ipaddress.ip_network(args.ip, strict=False)
            # Show network info instead
            args.cidr = args.ip
            return cmd_cidr(args)
        except ValueError as e:
            print(f"Invalid IP: {e}", file=sys.stderr)
            sys.exit(1)

    info = {
        'ip': str(ip),
        'version': f"IPv{ip.version}",
        'is_private': ip.is_private,
        'is_loopback': ip.is_loopback,
        'is_multicast': ip.is_multicast,
        'is_link_local': ip.is_link_local,
        'is_reserved': ip.is_reserved,
        'is_global': ip.is_global,
        'is_unspecified': ip.is_unspecified,
        'reverse_pointer': ip.reverse_pointer,
    }

    if args.format == 'json':
        print(json.dumps(info, indent=2))
    elif args.format == 'csv':
        w = csv.writer(sys.stdout)
        w.writerow(info.keys())
        w.writerow(info.values())
    else:
        print(f"IP:             {info['ip']}")
        print(f"Version:        {info['version']}")
        print(f"Private:        {info['is_private']}")
        print(f"Loopback:       {info['is_loopback']}")
        print(f"Multicast:      {info['is_multicast']}")
        print(f"Link-local:     {info['is_link_local']}")
        print(f"Reserved:       {info['is_reserved']}")
        print(f"Global:         {info['is_global']}")
        print(f"Unspecified:    {info['is_unspecified']}")
        print(f"PTR:            {info['reverse_pointer']}")


def main():
    parser = argparse.ArgumentParser(description='IP Utils')
    sub = parser.add_subparsers(dest='command', required=True)

    for name, help_text in [
        ('cidr', 'Calculate CIDR details'),
        ('expand', 'Expand CIDR to IP list'),
        ('range', 'Convert IP range to CIDR'),
        ('mask', 'Convert subnet mask notations'),
        ('validate', 'Validate IP/CIDR'),
        ('classify', 'Classify IP address'),
        ('batch', 'Process multiple IPs from file'),
        ('info', 'Detailed IP information'),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument('-f', '--format', choices=['text', 'json', 'csv'],
                       default='text', help='Output format')

    # cidr
    sub.choices['cidr'].add_argument('cidr', help='CIDR notation (e.g., 192.168.1.0/24)')
    sub.choices['cidr'].set_defaults(func=cmd_cidr)

    # expand
    sub.choices['expand'].add_argument('cidr', help='CIDR to expand')
    sub.choices['expand'].add_argument('--limit', type=int, default=256)
    sub.choices['expand'].set_defaults(func=cmd_expand)

    # range
    sub.choices['range'].add_argument('start', help='Start IP')
    sub.choices['range'].add_argument('end', help='End IP')
    sub.choices['range'].set_defaults(func=cmd_range)

    # mask
    sub.choices['mask'].add_argument('value', help='Mask value (dotted or prefix)')
    sub.choices['mask'].set_defaults(func=cmd_mask)

    # validate
    sub.choices['validate'].add_argument('ip', help='IP or CIDR to validate')
    sub.choices['validate'].set_defaults(func=cmd_validate)

    # classify
    sub.choices['classify'].add_argument('ip', help='IP to classify')
    sub.choices['classify'].set_defaults(func=cmd_classify)

    # batch
    sub.choices['batch'].add_argument('file', help='File with IPs (one per line)')
    sub.choices['batch'].set_defaults(func=cmd_batch)

    # info
    sub.choices['info'].add_argument('ip', help='IP to inspect')
    sub.choices['info'].set_defaults(func=cmd_info)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
