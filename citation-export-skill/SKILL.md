---
name: citation-export
description: Use this skill when the user provides academic paper titles, DOIs, or PMIDs and wants to generate citation files in EndNote (.enw), RIS (.ris), or RIS+ format. Supports single papers or batch processing of multiple references. Automatically searches PubMed, CrossRef, Semantic Scholar, and Google Scholar to retrieve complete bibliographic metadata.
---

# Citation Export Skill

## Overview

This skill generates citation files from academic paper titles, DOIs, or PMIDs. It supports multiple output formats (EndNote .enw, RIS .ris, RIS+) and can process single papers or batches of references. The skill automatically searches multiple academic databases to retrieve complete bibliographic metadata including authors, journal, year, volume, issue, pages, DOI, PMID, and abstract.

## Supported Output Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| EndNote | `.enw` | EndNote tagged format (RIS/EndNote Tagged) |
| RIS | `.ris` | Research Information Systems format |
| RIS+ | `.ris` | Extended RIS with additional fields (abstract, keywords, PMCID) |

## Workflow

### Step 1: Understand User Requirements

When a user requests citation files, identify:

- **Input type**: Paper titles, DOIs, or PMIDs
- **Number of papers**: Single paper or batch
- **Output format**: EndNote (.enw), RIS (.ris), or RIS+
- **Output location**: Where to save the files (default: workspace folder)

### Step 2: Search and Retrieve Metadata

For each paper, search databases in this priority order:

1. **PubMed** (for biomedical literature) - Use PMID or title search
2. **CrossRef API** - Use DOI or title search
3. **Semantic Scholar API** - Academic paper search
4. **Google Scholar** - Fallback for hard-to-find papers

#### Search Strategy

```
For each paper:
1. If PMID provided → Direct PubMed lookup
2. If DOI provided → CrossRef lookup
3. If title only → Search PubMed first, then CrossRef, then Google Scholar
4. Extract: authors, title, journal, year, volume, issue, pages, DOI, PMID, PMCID, abstract, keywords
```

### Step 3: Generate Citation File

Based on user's requested format, generate the appropriate file:

#### EndNote Format (.enw)

```
%0 Journal Article
%T [Title]
%A [Author1 Last, First]
%A [Author2 Last, First]
%J [Journal Name]
%D [Year]
%V [Volume]
%N [Issue]
%P [Pages]
%@ [ISSN]
%I [Publisher]
%X [Abstract]
%K [Keywords]
%M [PMID]
%U [DOI URL]
%G [Language]
%? [PMCID]
%6 [DOI]
```

#### RIS Format (.ris)

```
TY  - JOUR
TI  - [Title]
AU  - [Author1 Last, First]
AU  - [Author2 Last, First]
T2  - [Journal Name]
PY  - [Year]
VL  - [Volume]
IS  - [Issue]
SP  - [Start Page]
EP  - [End Page]
SN  - [ISSN]
PB  - [Publisher]
AB  - [Abstract]
KW  - [Keywords]
UR  - [DOI URL]
DO  - [DOI]
ER  - 
```

#### RIS+ Format (.ris)

Extended RIS with additional fields:
```
TY  - JOUR
TI  - [Title]
AU  - [Author1 Last, First]
...
M2  - PMID
M3  - PMCID
N1  - [Additional notes]
ER  - 
```

## Usage Examples

### Example 1: Single Paper by Title

User input:
```
Generate EndNote citation for: "A compact solution for vibrotactile proprioceptive feedback of wrist rotation and hand aperture"
```

Workflow:
1. Search PubMed for title → Find PMID 39135110
2. Retrieve full metadata from PubMed
3. Generate .enw file with all fields

### Example 2: Single Paper by DOI

User input:
```
Generate RIS file for DOI: 10.1186/s12984-024-01420-y
```

Workflow:
1. Query CrossRef API with DOI
2. Retrieve metadata
3. Generate .ris file

### Example 3: Single Paper by PMID

User input:
```
Generate citation for PMID: 39135110
```

Workflow:
1. Direct PubMed lookup
2. Retrieve full metadata
3. Generate citation file

### Example 4: Batch Processing

User input:
```
Generate EndNote citations for these papers:
1. A compact solution for vibrotactile proprioceptive feedback
2. Sensory stimulation for upper limb amputations modulates adaptability
3. A personalised prosthetic liner with embedded sensor technology
```

Workflow:
1. For each title, search databases
2. Collect all metadata
3. Generate single .enw file with multiple records (separated by blank lines)
4. Report any papers not found

### Example 5: Mixed Input with Reference Numbers

User input:
```
Generate RIS+ citations for:
228 A personalised prosthetic liner with embedded sensor technology: a case study
229 An Individual Prosthesis Control Method with Human Subjective Choices
230 Electrical stimulation therapy for peripheral nerve injury
```

Workflow:
1. Parse reference numbers and titles
2. Search each paper
3. Generate .ris file with reference numbers in notes
4. Include all available metadata

## Database Search APIs

### PubMed (NCBI E-utilities)

```
# Search by title
https://pubmed.ncbi.nlm.nih.gov/?term=[title]

# Fetch by PMID
https://pubmed.ncbi.nlm.nih.gov/[PMID]/

# E-utilities API
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=[PMID]
```

### CrossRef API

```
# Search by DOI
https://api.crossref.org/works/[DOI]

# Search by title
https://api.crossref.org/works?query.bibliographic=[title]&rows=1
```

### Semantic Scholar API

```
# Search by title
https://api.semanticscholar.org/graph/v1/paper/search?query=[title]

# Get paper details
https://api.semanticscholar.org/graph/v1/paper/[paperId]?fields=title,authors,year,venue,doi
```

## Handling Missing Information

When complete metadata cannot be found:

1. **Partial results**: Generate citation with available fields, mark missing fields as "Unknown"
2. **Chinese journals**: Search CNKI or use Chinese academic databases
3. **Conference papers**: May have limited metadata; include proceedings info
4. **Preprints**: Include arXiv/medRxiv identifier if available

Report to user:
- Successfully processed papers
- Papers with partial information
- Papers not found (with suggestions for manual search)

## Output File Naming

Default naming convention:
- Single paper: `[FirstAuthor]_[Year]_[JournalAbbrev].enw` or `.ris`
- Batch: `references_batch.enw` or `references_batch.ris`
- User can specify custom filename

## Quality Checklist

Before delivering citation file, verify:

- [ ] All authors included (check for "et al." truncation)
- [ ] Journal name is full name (not abbreviation)
- [ ] Year, volume, issue, pages are complete
- [ ] DOI is valid and resolves
- [ ] PMID/PMCID included for PubMed-indexed papers
- [ ] Abstract included if available
- [ ] Keywords included if available
- [ ] No "Unknown" fields remain (or user is notified)

## Common Issues and Solutions

### Issue: Paper not found in PubMed

Solution: Search CrossRef, then Google Scholar. For Chinese papers, the title may be an English translation of a Chinese paper - search with Chinese characters if available.

### Issue: Incomplete author list

Solution: CrossRef and PubMed usually have complete author lists. If truncated, visit the publisher's website directly.

### Issue: Missing page numbers

Solution: Some early-view/online-first articles don't have page numbers yet. Use article ID or DOI instead.

### Issue: Duplicate papers in batch

Solution: Detect and merge duplicates, keeping the record with more complete metadata.

## Integration with Reference Managers

### EndNote

1. Open EndNote
2. File → Import → Import File
3. Select the .enw file
4. Import Option: EndNote Import
5. Click Import

### Zotero

1. Open Zotero
2. File → Import
3. Select the .ris file
4. Choose "RIS" as import format

### Mendeley

1. Open Mendeley
2. File → Import → RIS
3. Select the .ris file

### JabRef

1. Open JabRef
2. File → Import into new library
3. Select the .ris or .enw file

## Notes

- Always prefer PMID/DOI lookup over title search for accuracy
- For biomedical papers, PubMed is the most reliable source
- For engineering/CS papers, CrossRef and Semantic Scholar are better
- Google Scholar should be used as a fallback
- Batch processing may take time for many papers - inform user of progress
- Save intermediate results to avoid re-searching if process is interrupted
