# Codex Session Retention v2 Design

## Goal

Provide a globally installable Codex Skill plus an independent terminal command that can make selected local Codex CLI and VS Code Codex sessions disappear from local session, archive, conversation, task, goal, memory, log, and session-index data. The command must be run after all Codex processes exit before any destructive mutation.

The retention default is seven 24-hour periods measured from each session's last activity time. A session exactly at the cutoff remains in the recent section and is not stale.

## Why the Skill and command are separate

A Skill runs inside a Codex process, and that process may hold the current session's SQLite/WAL files open. A Skill must therefore never perform the destructive deletion itself. It may explain the workflow and point to the command, while the independent terminal command performs listing, planning, deletion, recovery, and verification after Codex exits.

## Delivered surfaces

- `~/.codex/skills/codex-session-retention/SKILL.md` — trigger description and safe terminal workflow.
- `~/.local/bin/codex-session-retention` — executable wrapper for the implementation script.
- A standard-library Python implementation shared by the wrapper and Skill installation.
- An idempotent installer that atomically installs the Skill and wrapper, preserving the old installation in a temporary backup until the new installation validates.

No plugin command or MCP server is required in the first version. A plugin could later expose the read-only commands, but it must not move destructive deletion back into the Codex process.

## Commands and workflow

### `list`

```text
codex-session-retention list --days 7 [--root PATH]
```

Perform a read-only scan and print every discovered session. Numbering is valid only for that output. The report includes a cutoff line followed by all sessions whose last activity is at or after the cutoff, a separator, and all older sessions.

Each row contains number, canonical ID, last activity time, time source, title, path/status, file count, JSONL record count, and aggregate bytes. Database-only sessions are listed with `missing` rollout status.

### `plan`

```text
codex-session-retention plan --days 7 --select 8,9-11 [--root PATH] [--allow-fresh]
```

Re-scan the root, validate the selected numbers, and write a mode-0600 temporary manifest. The manifest contains IDs, selected rollout/snapshot paths, structured row targets, selected-artifact sizes, mtimes, and hashes; it contains no conversation body text. Global index/SQLite files are intentionally not frozen at plan time because closing Codex can checkpoint WAL files. By default only stale numbers are selectable. `--allow-fresh` is required for recent sessions and produces an explicit warning. Planning never mutates Codex data.

### `delete`

```text
codex-session-retention delete --manifest PATH --confirm DELETE --closed-confirmation CLOSED
```

Require exact confirmations, verify that every manifest fingerprint and canonical path is unchanged, and abort unless the target Codex root is readable/writable and no recovery journal is pending. This command is intended to run from a terminal after Codex CLI and VS Code Codex have exited.

### `recover`

```text
codex-session-retention recover --journal PATH
```

Restore the previous live files from a journal left by an interrupted replacement. Refuse all new deletion while recovery is pending. A successful recovery removes the journal only after fingerprints match the restored state.

All commands accept `--root`, defaulting to `$CODEX_HOME` and then `~/.codex`, and reject non-positive `--days` values.

## Discovery and ordering

Use `state_5.sqlite.threads` as preferred metadata when available. Read `id`, `updated_at_ms`, `recency_at_ms`, `title`, `rollout_path`, and `archived`. Include database-only rows even when their rollout is missing.

Supplement the database with `sessions/**/*.jsonl` and `archived_sessions/**/*.jsonl`. Extract IDs from rollout filenames or `session_meta.payload.id`; canonicalize UUIDs and deduplicate by ID. Accept database `rollout_path` only when its resolved path is a `.jsonl` file under `sessions/` or `archived_sessions/`. Shared canonical paths, conflicting ownership, symlink escapes, and paths to non-rollout files are quarantined and block deletion rather than being guessed.

Choose last activity in this order:

1. positive `threads.updated_at_ms`;
2. positive `threads.recency_at_ms`;
3. the newest recognized timestamp inside associated rollout records;
4. associated rollout file mtime.

Display the selected source. Titles use database title, then the first recognizable user message in a rollout, then `(untitled)`. Sort descending by last activity and then by canonical ID. Mark a session stale only when `last_activity < now - days * 86_400_000`.

For each session, report file count, non-empty JSONL record count, total bytes, all canonical associated paths, and missing/ambiguous status. Do not treat arbitrary mentions of an ID inside another conversation's text as ownership.

## Deletion scope

For selected canonical IDs, delete only data with a verified relationship:

- rollout files below `sessions/` and `archived_sessions/`;
- exact matching records in `session_index.jsonl` (`id`) and `history.jsonl` (`session_id`);
- `state_5.sqlite.threads` rows;
- `state_5.sqlite.thread_dynamic_tools` rows by `thread_id` and `thread_spawn_edges` rows where either endpoint is selected;
- `goals_1.sqlite.thread_goals` rows by `thread_id`;
- `memories_1.sqlite.stage1_outputs` rows by `thread_id`;
- `logs_2.sqlite.logs` rows by `thread_id`;
- `shell_snapshots` only when both the canonical session ID in the filename and `CODEX_THREAD_ID` in the content match.

Do not delete `auth.json`, `config.toml`, `installation_id`, `version.json`, Skills, plugins, project files, arbitrary SQLite databases, or unassociated shell snapshots. If a selected session has an ambiguous or shared association, abort the whole plan before mutation.

## Transaction, backup, and verification

Use a mode-0700 temporary transaction directory outside `.codex`. At delete time, after Codex has exited, fingerprint the current global index/SQLite/WAL files and stage JSONL edits and clean SQLite copies there. Copy affected SQLite databases using SQLite's backup API so live WAL/SHM state is captured consistently; apply SQL deletes to the staged copies and close them before replacement. Re-check these fresh global fingerprints immediately before live replacement; a change after staging aborts without mutation. This two-phase check permits normal Codex shutdown between plan and delete while still preventing concurrent writes during deletion.

Before replacement, verify staged data has no selected IDs in structured index/history rows, thread rows, goal/memory/log rows, spawn-edge endpoints, or session-owned paths. Maintain a journal containing original paths, backup paths, staged paths, and fingerprints. Replace live files with `os.replace` only after all staged validations pass. If any replacement fails, restore all originals from the journal. On process interruption, require `recover` before another delete. Remove the temporary manifest, journal, and backups only after post-replacement verification succeeds.

If an expected database is present but locked, unreadable, schema-incompatible, or missing a required session-linked table, stop before changing any layer. Optional databases that do not exist are reported as absent. A final report lists selected sessions, deleted files, deleted row counts per table, freed bytes, skipped/ambiguous data, and residual structured references.

## Safety rules

- `list` and `plan` are read-only.
- `delete` requires `DELETE` and `CLOSED` exact confirmations.
- Delete only canonical paths under the selected Codex root and only known rollout/snapshot locations.
- Refuse stale manifests, duplicate/shared ownership, schema drift, pending recovery journals, and unexpected database sidecars.
- Never silently continue after a partial failure.
- Never delete cloud-side history; this tool only controls local files/databases.

## Testing and live verification

Build a synthetic Codex home covering active/archive sessions, database-only rows, old filename with recent database activity, exact cutoff, missing rollout, duplicate/shared paths, symlink escape, non-rollout database paths, malformed JSONL, shell snapshot ambiguity, all dependent SQLite tables, WAL/SHM files, manifest drift, post-plan global-file changes, database locks, staged failure, replacement failure, and recovery.

Run the complete unit/integration suite and the Skill validator. Against the real Codex home, run only `list` and `plan` in read-only mode, compare representative rows with the local SQLite/index files, and never perform a real delete during development. A real delete is a separate user-initiated terminal operation after all Codex processes are closed.
