---
name: ingenic-kconfig-formatter
version: "1.0"
description: Format, validate, read, and modify Ingenic (君正半导体) KConfig configuration files — including Config.in (Kconfig definitions), .config (actual config/autoconf), and .config.in (config templates) — used in Ingenic SDK build systems based on Buildroot/Linux kernel Kconfig framework.
---

# Ingenic KConfig Formatter Skill (v1.0)

## Overview

This skill handles Ingenic (君正半导体) SoC SDK build system configuration files. Ingenic SDKs (X1000, X2000, T31, T40, etc.) use a Kconfig-based build system derived from Buildroot/Linux kernel. The skill covers three file types:

| File | Purpose | Example |
|------|---------|---------|
| **Config.in** | Kconfig definition files — define config options, menus, choices | `package/xxx/Config.in` |
| **.config** | Actual configuration file — stores selected values | `output/.config` |
| **.config.in** | Config template with default values | `board/ingenic/xxx/config.in` |
| **autoconf.h** | Generated C header from config (read-only, for reference) | `output/autoconf.h` |

## File Format Reference

### Config.in (Kconfig Definitions)

Config.in files define the configuration options structure. Syntax is based on Linux Kconfig.

#### Basic Syntax

```
# Comment line (starts with #)

menu "Menu Title"                          # Start a menu
    depends on !CONFIG_XXX                  # Optional dependency

config BR2_PACKAGE_XXX                     # Simple boolean option
    bool "Package XXX"
    default y                              # Default value
    help                                   # Help text follows
      This is the help description.
      It can span multiple lines.

config BR2_PACKAGE_XXX_VERSION             # String option
    string "Package XXX version"
    default "1.2.0"

config BR2_PACKAGE_XXX_FEATURE             # Option with choices
    int "Feature level"
    range 0 100
    default 50

choice                                      # Choice group (mutually exclusive)
    prompt "Selection mode"
    default BR2_PACKAGE_XXX_MODE_A

config BR2_PACKAGE_XXX_MODE_A
    bool "Mode A"

config BR2_PACKAGE_XXX_MODE_B
    bool "Mode B"

endchoice

endmenu                                     # End of menu
```

#### Key Directives

| Directive | Description |
|-----------|-------------|
| `menu` / `endmenu` | Menu grouping, supports nesting |
| `choice` / `endchoice` | Mutually exclusive choice group |
| `config` | Configuration option definition |
| `menuconfig` | Config option that can also act as a menu entry |
| `if` / `endif` | Conditional block |
| `source` | Include another Config.in file (similar to #include) |
| `comment` | Display-only comment in menuconfig UI |

#### Option Attributes

```
config BR2_PACKAGE_XXX
    bool "Description"          # Boolean: y/n
    # or
    tristate "Description"      # Tri-state: y/m/n (kernel only)
    # or
    string "Description"        # String value
    # or
    int "Description"           # Integer value
    # or
    hex "Description"           # Hexadecimal value
    default y                   # Default value
    depends on BR2_PACKAGE_YYY  # Dependency
    select BR2_PACKAGE_ZZZ      # Reverse dependency (force-select)
    help                        # Help text (indented by 2 spaces)
      Help line 1
      Help line 2
```

#### Ingenic-Specific Patterns

Ingenic SDKs often use custom prefixes instead of standard `BR2_`:

```
config INGENIC_X1000_FEATURE
    bool "Enable X1000 feature"

config T31_VIDEO_ENCODER
    bool "T31 video encoder support"
```

Common Ingenic config prefixes: `BR2_`, `INGENIC_`, `T31_`, `T40_`, `X1000_`, `X2000_`.

### .config File

The actual configuration file uses `key=value` format:

```
# Automatically generated file; DO NOT EDIT.
# Buildroot/Ingenic Configuration

CONFIG_XXX=y                              # Boolean enabled
# CONFIG_XXX is not set                   # Boolean disabled
CONFIG_XXX_STRING="value"                 # String
CONFIG_XXX_INT=123                        # Integer
CONFIG_XXX_HEX=0x7F                       # Hex

# Comments (from Config.in comment directives)
#
# Section header comments
#
```

### .config.in (Template)

Template config files define defaults for a specific board:

```
CONFIG_XXX=y
# CONFIG_YYY is not set
CONFIG_ZZZ="default_value"
```

## Workflow

### Step 1: Determine Task Type

Identify what the user needs:

| Task | Input | Output |
|------|-------|--------|
| **Format Config.in** | A Config.in file | Properly indented, validated Config.in |
| **Read/parse .config** | A .config file | Structured key-value listing |
| **Edit .config** | .config + changes | Updated .config |
| **Generate .config** | .config.in template | Filled .config (expand/merge) |
| **Validate** | Any KConfig file | Error report with line numbers |

### Step 2: Format Config.in

Apply the following formatting rules:

#### Indentation Rules

```
# Correct:
menu "Main Menu"                           # 0 indent
    menu "Sub Menu"                        # 4 spaces indent
        config BR2_PACKAGE_XXX             # 8 spaces indent
            bool "Package XXX"             # 12 spaces indent
            default y                      # 12 spaces indent
            help                           # 12 spaces indent
                This is help text.         # 14 spaces indent
    endmenu                                # 4 spaces indent
endmenu                                    # 0 indent

choice                                      # 0 or 4 indent (consistent)
    prompt "Choice"
    default BR2_PACKAGE_YYY_A
config BR2_PACKAGE_YYY_A
    bool "Option A"
config BR2_PACKAGE_YYY_B
    bool "Option B"
endchoice
```

**Indentation levels (4 spaces per level)**:

| Level | Context | Indent |
|-------|---------|--------|
| 0 | Top-level: `menu`, `endmenu`, `source`, `if`, `endif`, top `choice` | 0 |
| 1 | Inside menu/choice: nested `menu`, `config`, `choice` | 4 |
| 2 | Inside nested menu: `config`, `menuconfig` | 8 |
| 3 | Config attributes: `bool`, `string`, `default`, `depends on`, `select`, `range` | 12 |
| 4 | `help` keyword and help body | 12 for keyword, 14 for text |

#### Spacing Rules

- 1 space between directive and value: `bool "text"`, `default y`
- 1 space around `=` in `depends on` / `select` if applicable
- 1 blank line between separate `config` blocks (optional but recommended)
- No trailing whitespace on any line

#### Sorting Rules

For `.config` files (not Config.in):

- Group by prefix: `CONFIG_*`, `INGENIC_*`, etc.
- Within each group, sort alphabetically
- Commented-out entries (`# CONFIG_XXX is not set`) sorted alongside enabled ones
- Keep `# Automatically generated` header as first line

### Step 3: Parse .config

When reading a .config file, extract structured data:

```json
{
  "entries": [
    {
      "key": "CONFIG_XXX",
      "value": "y",
      "type": "boolean",
      "enabled": true
    },
    {
      "key": "CONFIG_YYY",
      "value": "n",
      "type": "boolean",
      "enabled": false,
      "raw": "# CONFIG_YYY is not set"
    },
    {
      "key": "CONFIG_ZZZ",
      "value": "\"1.0.0\"",
      "type": "string",
      "enabled": true
    }
  ],
  "header": "Automatically generated file; DO NOT EDIT."
}
```

#### Parsing Rules

1. Lines starting with `CONFIG_` or custom prefix → active config entry
2. Lines matching `# CONFIG_XXX is not set` → disabled boolean entry
3. Lines starting with `#` (other than disabled entries) → comments
4. Empty lines → preserved as section separators
5. `=y` → boolean enabled
6. `=n` → boolean disabled
7. `="..."` → string (strip quotes from value)
8. `=<number>` → integer
9. `=0x...` → hexadecimal

### Step 4: Edit .config

When modifying a .config file:

1. Parse the existing .config
2. Apply user's changes (add/modify/remove entries)
3. Validate the modified config
4. Output the updated .config

**Change format examples**:

```
# User can specify changes as:
CONFIG_XXX=y                    # Set XXX to y
CONFIG_YYY=n                    # Set YYY to n (or use # CONFIG_YYY is not set)
CONFIG_ZZZ="new_value"          # Set string value
# CONFIG_AAA is not set         # Disable AAA
+CONFIG_NEW=y                   # Add new entry
-CONFIG_OLD                     # Remove entry
```

### Step 5: Validate

Check for common errors:

#### Config.in Validation

- [ ] Unclosed `menu` (missing `endmenu`)
- [ ] Unclosed `choice` (missing `endchoice`)
- [ ] Mismatched `if`/`endif`
- [ ] Duplicate `config` entries with the same name
- [ ] `source` pointing to nonexistent files
- [ ] Invalid indentation (inconsistent levels)
- [ ] `default` without a matching type attribute
- [ ] `depends on` referencing undefined config symbols
- [ ] `select` creating circular dependencies

#### .config Validation

- [ ] All values valid for their type (bool: y/n, int: numeric, etc.)
- [ ] No duplicate keys
- [ ] No syntax errors in value format

### Step 6: Generate .config from Template

When generating a `.config` from a `.config.in` template:

1. Parse the `.config.in` template
2. Optionally merge with board defaults from `board/ingenic/*/`
3. Apply any user overrides
4. Sort entries alphabetically
5. Add the auto-generated header comment
6. Output the `.config`

## Common Scenarios

### Scenario 1: Format a Messy Config.in

**Input** (bad indentation, inconsistent spacing):

```
menu "Multimedia"
config BR2_PACKAGE_XXX
bool "XXX"
default y
config BR2_PACKAGE_YYY
    string "YYY version"
default "2.0"
help
  YYY help text
endmenu
```

**Output** (formatted):

```
menu "Multimedia"

config BR2_PACKAGE_XXX
    bool "XXX"
    default y

config BR2_PACKAGE_YYY
    string "YYY version"
    default "2.0"
    help
        YYY help text

endmenu
```

### Scenario 2: Enable/Disable Config Entries

**User request**: "Enable CONFIG_XXX, disable CONFIG_YYY, set CONFIG_ZZZ to 3"

**Input .config**:
```
CONFIG_XXX=n
CONFIG_YYY=y
CONFIG_ZZZ=1
```

**Output .config**:
```
CONFIG_XXX=y
# CONFIG_YYY is not set
CONFIG_ZZZ=3
```

### Scenario 3: Merge Two .config Files

When merging two config partials:
1. Parse both files
2. Apply priority rules (user overrides base)
3. Detect conflicts and report to user
4. Output merged result

## Rules

1. **Preserve comments** — Do not remove user comments from `.config` unless requested
2. **Preserve section structure** — Keep blank-line-separated sections intact
3. **Backward compatibility** — Do not rename config symbols
4. **Validate before writing** — Always validate the output before generating files
5. **Report warnings** — Surface potential issues (duplicates, undefined refs) to the user
6. **Config.in format uses 4-space indentation** — Never use tabs for Config.in
7. **.config alphabetically sorted** — Except the auto-generated header line
