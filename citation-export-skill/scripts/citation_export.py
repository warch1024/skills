#!/usr/bin/env python3
"""
Citation Export Script
Generates citation files in EndNote (.enw), RIS (.ris), or RIS+ format
from academic paper metadata.

Usage:
    python citation_export.py --input metadata.json --format enw --output references.enw
    python citation_export.py --input metadata.json --format ris --output references.ris
    python citation_export.py --input metadata.json --format ris+ --output references.ris
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Optional


def parse_pages(pages: str) -> tuple:
    """Parse page range into start and end pages."""
    if not pages:
        return None, None
    if '-' in pages:
        parts = pages.split('-')
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None
    return pages.strip(), None


def format_authors_enw(authors: List[str]) -> str:
    """Format authors for EndNote format."""
    lines = []
    for author in authors:
        # Handle "Last, First" or "First Last" format
        if ',' in author:
            lines.append(f"%A {author}")
        else:
            parts = author.split()
            if len(parts) >= 2:
                last = parts[-1]
                first = ' '.join(parts[:-1])
                lines.append(f"%A {last}, {first}")
            else:
                lines.append(f"%A {author}")
    return '\n'.join(lines)


def format_authors_ris(authors: List[str]) -> str:
    """Format authors for RIS format."""
    lines = []
    for author in authors:
        if ',' in author:
            lines.append(f"AU  - {author}")
        else:
            parts = author.split()
            if len(parts) >= 2:
                last = parts[-1]
                first = ' '.join(parts[:-1])
                lines.append(f"AU  - {last}, {first}")
            else:
                lines.append(f"AU  - {author}")
    return '\n'.join(lines)


def generate_endnote(paper: Dict) -> str:
    """Generate EndNote (.enw) format citation."""
    lines = ['%0 Journal Article']
    
    if paper.get('title'):
        lines.append(f"%T {paper['title']}")
    
    if paper.get('authors'):
        for author in paper['authors']:
            if ',' in author:
                lines.append(f"%A {author}")
            else:
                parts = author.split()
                if len(parts) >= 2:
                    last = parts[-1]
                    first = ' '.join(parts[:-1])
                    lines.append(f"%A {last}, {first}")
                else:
                    lines.append(f"%A {author}")
    
    if paper.get('journal'):
        lines.append(f"%J {paper['journal']}")
    
    if paper.get('year'):
        lines.append(f"%D {paper['year']}")
    
    if paper.get('volume'):
        lines.append(f"%V {paper['volume']}")
    
    if paper.get('issue'):
        lines.append(f"%N {paper['issue']}")
    
    if paper.get('pages'):
        lines.append(f"%P {paper['pages']}")
    
    if paper.get('issn'):
        lines.append(f"%@ {paper['issn']}")
    
    if paper.get('publisher'):
        lines.append(f"%I {paper['publisher']}")
    
    if paper.get('abstract'):
        lines.append(f"%X {paper['abstract']}")
    
    if paper.get('keywords'):
        lines.append(f"%K {paper['keywords']}")
    
    if paper.get('pmid'):
        lines.append(f"%M {paper['pmid']}")
    
    if paper.get('doi'):
        lines.append(f"%U https://doi.org/{paper['doi']}")
    
    if paper.get('language'):
        lines.append(f"%G {paper['language']}")
    
    if paper.get('pmcid'):
        lines.append(f"%? {paper['pmcid']}")
    
    if paper.get('doi'):
        lines.append(f"%6 {paper['doi']}")
    
    return '\n'.join(lines)


def generate_ris(paper: Dict, extended: bool = False) -> str:
    """Generate RIS (.ris) format citation."""
    lines = ['TY  - JOUR']
    
    if paper.get('title'):
        lines.append(f"TI  - {paper['title']}")
    
    if paper.get('authors'):
        for author in paper['authors']:
            if ',' in author:
                lines.append(f"AU  - {author}")
            else:
                parts = author.split()
                if len(parts) >= 2:
                    last = parts[-1]
                    first = ' '.join(parts[:-1])
                    lines.append(f"AU  - {last}, {first}")
                else:
                    lines.append(f"AU  - {author}")
    
    if paper.get('journal'):
        lines.append(f"T2  - {paper['journal']}")
    
    if paper.get('year'):
        lines.append(f"PY  - {paper['year']}")
    
    if paper.get('volume'):
        lines.append(f"VL  - {paper['volume']}")
    
    if paper.get('issue'):
        lines.append(f"IS  - {paper['issue']}")
    
    if paper.get('pages'):
        start, end = parse_pages(paper['pages'])
        if start:
            lines.append(f"SP  - {start}")
        if end:
            lines.append(f"EP  - {end}")
    
    if paper.get('issn'):
        lines.append(f"SN  - {paper['issn']}")
    
    if paper.get('publisher'):
        lines.append(f"PB  - {paper['publisher']}")
    
    if paper.get('abstract'):
        lines.append(f"AB  - {paper['abstract']}")
    
    if paper.get('keywords'):
        for kw in paper['keywords'].split(';'):
            kw = kw.strip()
            if kw:
                lines.append(f"KW  - {kw}")
    
    if paper.get('doi'):
        lines.append(f"UR  - https://doi.org/{paper['doi']}")
        lines.append(f"DO  - {paper['doi']}")
    
    # RIS+ extended fields
    if extended:
        if paper.get('pmid'):
            lines.append(f"M2  - {paper['pmid']}")
        
        if paper.get('pmcid'):
            lines.append(f"M3  - {paper['pmcid']}")
        
        if paper.get('notes'):
            lines.append(f"N1  - {paper['notes']}")
    
    lines.append('ER  - ')
    
    return '\n'.join(lines)


def generate_citations(papers: List[Dict], format_type: str) -> str:
    """Generate citations for all papers in specified format."""
    citations = []
    
    for paper in papers:
        if format_type == 'enw':
            citations.append(generate_endnote(paper))
        elif format_type == 'ris':
            citations.append(generate_ris(paper, extended=False))
        elif format_type == 'ris+':
            citations.append(generate_ris(paper, extended=True))
    
    return '\n\n'.join(citations)


def main():
    parser = argparse.ArgumentParser(description='Generate citation files')
    parser.add_argument('--input', '-i', required=True, help='Input JSON file with paper metadata')
    parser.add_argument('--format', '-f', required=True, choices=['enw', 'ris', 'ris+'],
                        help='Output format: enw (EndNote), ris (RIS), ris+ (RIS extended)')
    parser.add_argument('--output', '-o', required=True, help='Output file path')
    
    args = parser.parse_args()
    
    # Read input
    with open(args.input, 'r', encoding='utf-8') as f:
        papers = json.load(f)
    
    # Generate citations
    content = generate_citations(papers, args.format)
    
    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Generated {len(papers)} citations in {args.format} format: {args.output}")


if __name__ == '__main__':
    main()
