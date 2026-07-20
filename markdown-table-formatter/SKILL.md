---
name: markdown-table-formatter
version: "1.0"
description: Help users format, clean up, align, and fix markdown tables. Automatically aligns columns, normalizes separators, trims whitespace, adjusts column widths, and can convert between different table styles. Supports standard GFM tables, pipe tables, and grid tables.
---

# Markdown Table Formatter Skill (v1.0)

## Overview

This skill formats and beautifies markdown tables. It helps users clean up messy tables, align columns properly, normalize separators, and convert between different table styles.

## Core Capabilities

| Capability | Description |
|-----------|-------------|
| **Column Alignment** | Auto-align columns based on content (left/right/center) |
| **Whitespace Trimming** | Remove extra spaces around cell content |
| **Width Normalization** | Make all columns equal width based on longest content |
| **Separator Fixing** | Fix malformed `---|---` separator rows |
| **Style Conversion** | Convert between pipe tables, GFM tables, and grid tables |
| **Empty Cell Filling** | Fill empty cells with `-` or keep as-is |

## Input Format Detection

The skill auto-detects the input table format:

1. **Pipe Table** — Most common, uses `|` pipes
   ```
   | Header 1 | Header 2 |
   |----------|----------|
   | Cell 1   | Cell 2   |
   ```

2. **Simple/Gfm Table** — Without leading/trailing pipes
   ```
   Header 1 | Header 2
   ---------|---------
   Cell 1   | Cell 2
   ```

3. **Grid Table** — Uses `+---+` borders (reStructuredText style)
   ```
   +----------+----------+
   | Header 1 | Header 2 |
   +==========+==========+
   | Cell 1   | Cell 2   |
   +----------+----------+
   ```

## Formatting Rules

### Separator Row Rules

The separator row (the second row in a pipe table) controls alignment:

| Alignment | Left | Center | Right |
|-----------|------|--------|-------|
| Separator | `:---` | `:---:` | `---:` |
| Min dashes | 3 | 3 | 3 |

### Minimum Column Width

Each column should be at least as wide as:
- The longest cell content in that column, OR
- 3 characters (for separator row minimum)

Whichever is **larger**.

### Padding Rules

- Each cell should have **1 space** of padding on each side
- The leading `|` should be followed by 1 space
- The trailing `|` should be preceded by 1 space

### No Trailing Whitespace

- No trailing spaces after the last `|` on each row
- No trailing blank lines at the end of the table (except 1 blank line if needed)

## Workflow

### Step 1: Understand the User's Request

Determine what the user wants:

- **Format a table**: Align columns, fix separators, normalize widths
- **Convert table style**: Pipe → GFM, GFM → Grid, etc.
- **Fix a broken table**: Malformed separator rows, mismatched column counts
- **Extract table**: From markdown document or raw text

### Step 2: Parse the Input

1. Identify the table boundaries (look for `|` lines or `+---+` lines)
2. Split into rows
3. Identify header row, separator row, and body rows
4. Determine column count from the row with the most columns

### Step 3: Handle Column Count Mismatches

If rows have different numbers of columns:
- **Short rows**: Pad with empty cells
- **Long rows**: Truncate to match the separator row
- **No separator row**: Use the header row count

### Step 4: Apply Formatting

For each column, calculate the maximum content width:

```
max_width = max(len(cell) for cell in column_cells)
```

Then for each cell, pad to `max_width + 2` (1 space each side).

Generate the separator row based on alignment:
- Left: `:---` (pad with `-` to match width-2)
- Center: `:---:` (pad with `-` to match width-2)
- Right: `---:` (pad with `-` to match width-2)

### Step 5: Output the Result

Return the formatted table with:
- All columns aligned
- Proper separator row
- Consistent formatting throughout

## Output Examples

### Input (messy):

```
|Name|Age|City|
|---|---|---|
|Alice|30|New York|
|Bob|25|San Francisco|
```

### Output (formatted):

```
| Name  | Age | City          |
|-------|-----|---------------|
| Alice | 30  | New York      |
| Bob   | 25  | San Francisco |
```

## Common Issues and Fixes

### Issue: Missing separator row

If the table has no separator row, add one with all columns left-aligned.

### Issue: Inconsistent column counts

If body rows have more columns than the header:
- Warn the user about the extra columns
- Use the header column count
- Put extra column content in the last column (separated by brute force within cell)

If the header has more columns than body rows:
- Pad body rows with empty cells

### Issue: Mixed alignment in same column

Use the most common alignment, or default to left.

### Issue: Escaped pipes in cells

If a cell contains `\|` (escaped pipe), do NOT treat it as a column separator.

## Quality Checklist

- [ ] All columns have consistent widths
- [ ] Separator row uses correct alignment markers (`:---`, `:---:`, `---:`)
- [ ] Padding is exactly 1 space on each side
- [ ] No trailing whitespace on any line
- [ ] Column count is consistent across all rows
- [ ] Empty cells are handled properly
- [ ] Escaped pipes are preserved
- [ ] Table has exactly one blank line before and after (if in a document)

## Rules

1. **Preserve original data** — Do not modify cell content (except trimming whitespace)
2. **Do not merge cells** — Keep each cell as-is
3. **Do not reorder columns or rows** — Preserve the original layout
4. **Minimum dashes = 3** — Even for columns with very short content
5. **User can specify alignment** — Per-column or global (default: left-aligned)
