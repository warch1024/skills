# Codex Session Retention v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a global Codex Skill and independent terminal command that safely lists, plans, fully deletes, verifies, and recovers local Codex session removal after Codex exits.

**Architecture:** A Python standard-library package separates discovery, display, manifest creation, staged transformations, transaction/recovery, and CLI orchestration. Destructive work happens only on staged copies; a durable journal protects the short live replacement phase. The installed Skill documents and invokes only read-only workflow guidance, while the external wrapper runs the terminal command.

**Tech Stack:** Python 3.10+ standard library (`argparse`, `dataclasses`, `datetime`, `hashlib`, `json`, `os`, `pathlib`, `shutil`, `sqlite3`, `tempfile`, `unittest`), Codex Skill metadata, POSIX shell wrapper.

---

## File map

- Modify: `SKILL.md` — concise safe workflow; never tells Codex to execute destructive deletion in its own process.
- Modify: `agents/openai.yaml` — UI metadata and default read-only prompt.
- Delete after replacement tests exist: `scripts/cleanup_codex_sessions.py` — incomplete v1 implementation.
- Create: `scripts/codex_session_retention.py` — thin executable CLI entry.
- Create: `scripts/retention/__init__.py` — public package exports.
- Create: `scripts/retention/model.py` — immutable session, fingerprint, manifest, report, and journal models.
- Create: `scripts/retention/discovery.py` — read-only SQLite/rollout/snapshot discovery and ordering.
- Create: `scripts/retention/display.py` — table formatting, size/time formatting, selection parsing.
- Create: `scripts/retention/manifest.py` — fingerprinting and mode-0600 manifest serialization/validation.
- Create: `scripts/retention/staging.py` — staged JSONL/SQLite transformations and residual checks.
- Create: `scripts/retention/transaction.py` — journaled live replacement and recovery.
- Create: `scripts/retention/cli.py` — `list`, `plan`, `delete`, and `recover` orchestration.
- Create: `scripts/install.py` — atomic Skill/wrapper installer.
- Create: `tests/fixtures.py` — synthetic Codex home and schema builders.
- Replace: `tests/test_cleanup_codex_sessions.py` with focused test modules below.
- Create: `tests/test_discovery.py`, `tests/test_display.py`, `tests/test_manifest.py`, `tests/test_staging.py`, `tests/test_transaction.py`, `tests/test_cli.py`, `tests/test_install.py`.
- Remove during cleanup: repository `__pycache__/` artifacts; never install tests or caches into the global Skill.

The tracked `README.md` is outside the installed Skill payload and remains unchanged. The existing untracked v1 files are known partial work from the failed attempt; replace them only through the test-first tasks below.

### Task 1: Define v2 models and synthetic Codex-home fixtures

**Files:**
- Create: `scripts/retention/model.py`
- Create: `scripts/retention/__init__.py`
- Create: `tests/fixtures.py`
- Create: `tests/test_model.py`

- [ ] **Step 1: Write the model contract tests first**

```python
from pathlib import Path
from scripts.retention.model import SessionRecord

def test_session_record_stale_boundary_is_strict():
    cutoff_ms = 2_000_000_000_000
    record = SessionRecord(
        session_id="019f209c-8aea-71a0-9342-9e9a92a03286",
        last_activity_ms=cutoff_ms,
        activity_source="updated_at_ms",
        title="Boundary",
        paths=(Path("/tmp/codex/sessions/boundary.jsonl"),),
        snapshot_paths=(),
        file_count=1,
        record_count=1,
        size_bytes=10,
        archived=False,
        ambiguous=(),
    )
    assert record.is_stale(cutoff_ms) is False
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_model -v`

Expected: import failure because `scripts.retention.model` does not exist.

- [ ] **Step 3: Implement immutable core models**

Define frozen dataclasses with JSON-safe conversion methods:

```python
@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    last_activity_ms: int
    activity_source: str
    title: str
    paths: tuple[Path, ...]
    snapshot_paths: tuple[Path, ...]
    file_count: int
    record_count: int
    size_bytes: int
    archived: bool
    ambiguous: tuple[str, ...]

    def is_stale(self, cutoff_ms: int) -> bool:
        return self.last_activity_ms < cutoff_ms

@dataclass(frozen=True)
class FileFingerprint:
    path: Path
    exists: bool
    size: int
    mtime_ns: int
    sha256: str

@dataclass(frozen=True)
class ManifestSession:
    session_id: str
    last_activity_ms: int
    rollout_paths: tuple[Path, ...]
    snapshot_paths: tuple[Path, ...]

@dataclass(frozen=True)
class Manifest:
    version: int
    root: Path
    created_at_ms: int
    cutoff_ms: int
    selected: tuple[ManifestSession, ...]
    fingerprints: tuple[FileFingerprint, ...]

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(item.session_id for item in self.selected)

@dataclass(frozen=True)
class DeletionReport:
    session_count: int
    deleted_files: int
    deleted_jsonl_rows: int
    deleted_sqlite_rows: dict[str, int]
    freed_bytes: int
    residual_references: tuple[str, ...]

@dataclass(frozen=True)
class StagedDeletion:
    root: Path
    transaction_dir: Path
    replacements: tuple[tuple[Path, Path], ...]
    deletion_paths: tuple[Path, ...]
    jsonl_rows: tuple[tuple[str, int], ...]
    sqlite_rows: tuple[tuple[str, int], ...]
    freed_bytes: int
    journal_path: Path
```

Add fixture helpers that create exact `threads`, `thread_dynamic_tools`, `thread_spawn_edges`, `thread_goals`, `stage1_outputs`, and `logs` schemas in a temporary root, plus JSONL rollout/index/history and verified/mismatched shell snapshots.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_model -v`

Expected: the strict-boundary and dataclass serialization tests pass.

- [ ] **Step 5: Commit the checkpoint**

```bash
git add scripts/retention tests/fixtures.py tests/test_model.py
git commit -m "test: define session retention v2 models"
```

### Task 2: Implement read-only discovery and complete listing (TDD)

**Files:**
- Create: `scripts/retention/discovery.py`
- Create: `scripts/retention/display.py`
- Create: `tests/test_discovery.py`
- Create: `tests/test_display.py`

- [ ] **Step 1: Write failing discovery tests**

Cover database-first metadata, database-only rows, active/archive rollouts, old filenames with recent DB activity, timestamp fallback, exact cutoff, first-user-message title, record/byte aggregation, canonical UUIDs, shared/conflicting paths, symlink escape, non-rollout DB paths, and two-factor shell snapshot matching.

```python
def test_activity_priority_and_full_ordering(self):
    records = discover_sessions(self.root, now_ms=NOW_MS, retention_days=7)
    self.assertEqual([r.session_id for r in records], [RECENT_DB_ID, RECENT_EVENT_ID, STALE_ID])
    self.assertEqual(records[0].activity_source, "updated_at_ms")
    self.assertEqual(records[1].activity_source, "rollout_timestamp")
    self.assertTrue(records[2].is_stale(NOW_MS - 7 * DAY_MS))

def test_snapshot_requires_filename_and_content_id(self):
    records = discover_sessions(self.root, now_ms=NOW_MS, retention_days=7)
    by_id = {record.session_id: record for record in records}
    self.assertEqual(by_id[TARGET_ID].snapshot_paths, (self.verified_snapshot,))
    self.assertIn("shell snapshot identity mismatch", by_id[TARGET_ID].ambiguous)
```

- [ ] **Step 2: Verify discovery RED**

Run: `python3 -m unittest tests.test_discovery -v`

Expected: import failure because `discover_sessions` is missing.

- [ ] **Step 3: Implement discovery with explicit ownership rules**

Implement:

```python
def discover_sessions(root: Path, now_ms: int, retention_days: int) -> list[SessionRecord]:
    """Return every canonical local session, newest activity first."""
```

Open `state_5.sqlite` using URI `mode=ro`; use DB `updated_at_ms`, then `recency_at_ms`, then maximum parsed ISO-8601/epoch rollout timestamp, then mtime. Resolve and accept only `.jsonl` paths under `sessions/` or `archived_sessions/`. Quarantine canonical paths owned by multiple DB rows or conflicting DB/file identities. Include DB-only rows with missing rollout status. Recognize snapshots only when filename UUID and parsed `CODEX_THREAD_ID` both equal the session ID.

- [ ] **Step 4: Verify discovery GREEN**

Run: `python3 -m unittest tests.test_discovery -v`

Expected: all discovery and ambiguity tests pass without writing to the root.

- [ ] **Step 5: Write failing display and selection tests**

```python
def test_listing_has_recent_and_stale_sections(self):
    text = format_session_table(self.records, cutoff_ms=self.cutoff_ms)
    self.assertIn("最近 7 天", text)
    self.assertIn("大于 7 天", text)
    self.assertLess(text.index(RECENT_ID), text.index("大于 7 天"))
    self.assertLess(text.index("大于 7 天"), text.index(STALE_ID))

def test_selection_parser_accepts_ranges_and_rejects_duplicates(self):
    self.assertEqual(parse_selection("8,9-11", 12), (8, 9, 10, 11))
    with self.assertRaises(SelectionError):
        parse_selection("8,8", 12)
```

- [ ] **Step 6: Verify display RED, implement, and verify GREEN**

Run RED: `python3 -m unittest tests.test_display -v`

Implement `format_session_table`, `format_bytes`, `format_local_time`, and `parse_selection`. Always show full ID, local timestamp plus source, title, paths/status, file count, record count, and bytes. Number the entire sorted result once and insert the separator before the first stale row.

Run GREEN: `python3 -m unittest tests.test_display -v`

Expected: complete two-section formatting and strict selection validation pass.

- [ ] **Step 7: Commit the checkpoint**

```bash
git add scripts/retention/discovery.py scripts/retention/display.py tests/test_discovery.py tests/test_display.py
git commit -m "feat: discover and list local codex sessions"
```

### Task 3: Create immutable deletion manifests (TDD)

**Files:**
- Create: `scripts/retention/manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Write failing manifest tests**

Test stale-only selection, `allow_fresh`, ambiguity refusal, canonical path containment, SHA-256 fingerprints for rollouts/index/history/databases/sidecars/snapshots, mode 0600, round-trip serialization, version validation, and drift rejection.

```python
def test_manifest_rejects_fresh_without_explicit_override(self):
    with self.assertRaises(FreshSessionError):
        build_manifest(self.root, self.records, (1,), self.cutoff_ms, allow_fresh=False)

def test_manifest_detects_changed_file(self):
    manifest = build_manifest(self.root, self.records, (2,), self.cutoff_ms, allow_fresh=False)
    self.history.write_text("changed\n", encoding="utf-8")
    with self.assertRaises(ManifestDriftError):
        validate_manifest(manifest)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_manifest -v`

Expected: import failure because manifest functions do not exist.

- [ ] **Step 3: Implement manifest construction and validation**

Provide exact APIs:

```python
def fingerprint(path: Path) -> FileFingerprint:
    path = path.resolve(strict=False)
    if not path.exists():
        return FileFingerprint(path, False, 0, 0, "")
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return FileFingerprint(path, True, stat.st_size, stat.st_mtime_ns, digest.hexdigest())

def build_manifest(root: Path, records: list[SessionRecord], selected_numbers: tuple[int, ...], cutoff_ms: int, allow_fresh: bool) -> Manifest:
    selected_records = tuple(records[number - 1] for number in selected_numbers)
    if not allow_fresh and any(not item.is_stale(cutoff_ms) for item in selected_records):
        raise FreshSessionError("recent sessions require --allow-fresh")
    if any(item.ambiguous for item in selected_records):
        raise AmbiguousOwnershipError("selected session has ambiguous ownership")
    selected = tuple(
        ManifestSession(item.session_id, item.last_activity_ms, item.paths, item.snapshot_paths)
        for item in selected_records
    )
    paths = collect_manifest_paths(root, selected)
    return Manifest(1, root.resolve(), now_ms(), cutoff_ms, selected, tuple(fingerprint(path) for path in paths))

def write_manifest(manifest: Manifest, output: Path | None = None) -> Path:
    destination = output or default_manifest_path()
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(manifest.to_dict(), handle, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
    return destination

def read_manifest(path: Path) -> Manifest:
    with path.open(encoding="utf-8") as handle:
        return Manifest.from_dict(json.load(handle))

def validate_manifest(manifest: Manifest) -> None:
    if manifest.version != 1:
        raise ManifestVersionError(manifest.version)
    for expected in manifest.fingerprints:
        if fingerprint(expected.path) != expected:
            raise ManifestDriftError(str(expected.path))
```

Implement the referenced `collect_manifest_paths`, `now_ms`, `default_manifest_path`, `to_dict`, and `from_dict` helpers in the same task with deterministic JSON field names. Hash only files needed for structured deletion or association. Store IDs/path metadata but no conversation text. Resolve every path and require it to be one of the known root/index/database/sidecar/rollout/snapshot targets. Reject selected records with ambiguity, shared ownership, or recent activity unless overridden.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_manifest -v`

Expected: manifest permissions, serialization, freshness protection, and drift checks pass.

- [ ] **Step 5: Commit the checkpoint**

```bash
git add scripts/retention/manifest.py tests/test_manifest.py
git commit -m "feat: create immutable session deletion manifests"
```

### Task 4: Transform JSONL and SQLite only in staging (TDD)

**Files:**
- Create: `scripts/retention/staging.py`
- Create: `tests/test_staging.py`

- [ ] **Step 1: Write failing staging tests**

Build a synthetic home with selected and unrelated records in every known table/file. Assert that staging removes exact structured IDs only, preserves arbitrary text mentions, captures WAL data through SQLite backup, refuses incompatible schemas, and leaves the live home byte-for-byte unchanged.

```python
def test_stage_removes_only_structured_session_references(self):
    before = snapshot_tree(self.root)
    staged = stage_deletion(self.manifest, self.transaction_dir)
    self.assertEqual(snapshot_tree(self.root), before)
    self.assertEqual(staged.sqlite_rows["state_5.sqlite.threads"], 1)
    self.assertEqual(staged.sqlite_rows["state_5.sqlite.thread_spawn_edges"], 2)
    self.assertEqual(staged.jsonl_rows["history.jsonl"], 3)
    self.assertIn(TARGET_ID, self.unrelated_rollout.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_staging -v`

Expected: import failure because `stage_deletion` is missing.

- [ ] **Step 3: Implement staged JSONL rewriting**

Parse each non-empty line as JSON. Remove a `session_index.jsonl` record only when top-level `id` is selected, and a `history.jsonl` record only when top-level `session_id` is selected. Preserve malformed lines and unrelated textual mentions byte-for-byte. Write staged replacements with original mode bits.

- [ ] **Step 4: Implement staged SQLite backups and exact SQL**

Use `sqlite3.Connection.backup()` from live source to a staged database. Validate required tables/columns before deleting. Execute parameterized statements inside one staged transaction:

```sql
DELETE FROM thread_dynamic_tools WHERE thread_id IN (:selected_ids);
DELETE FROM thread_spawn_edges WHERE parent_thread_id IN (:selected_ids) OR child_thread_id IN (:selected_ids);
DELETE FROM threads WHERE id IN (:selected_ids);
DELETE FROM thread_goals WHERE thread_id IN (:selected_ids);
DELETE FROM stage1_outputs WHERE thread_id IN (:selected_ids);
DELETE FROM logs WHERE thread_id IN (:selected_ids);
```

At runtime replace each `:selected_ids` marker with `",".join("?" for _ in selected_ids)` and pass the selected ID tuple as parameters; for the spawn-edge query pass the tuple twice.

Treat missing database files as optional/absent. If an existing known database cannot open or has a required table without required columns, raise before a live mutation. Close staged connections and run `PRAGMA integrity_check`.

- [ ] **Step 5: Implement residual verification and verify GREEN**

Check staged JSONL structured fields, every known table, edge endpoints, staged rollout/snapshot deletion set, and SQLite integrity. Return exact file/row/byte counts.

Run: `python3 -m unittest tests.test_staging -v`

Expected: all staged transformations pass and every test proves live files are unchanged.

- [ ] **Step 6: Commit the checkpoint**

```bash
git add scripts/retention/staging.py tests/test_staging.py
git commit -m "feat: stage complete session record removal"
```

### Task 5: Add journaled replacement and recovery (TDD)

**Files:**
- Create: `scripts/retention/transaction.py`
- Create: `tests/test_transaction.py`

- [ ] **Step 1: Write failing commit/recovery tests**

Use fault injection after each replacement position. Assert successful commit deletes selected rollouts/snapshots and installs staged JSONL/SQLite, while every injected failure restores exact original hashes. Simulate process death by leaving a journal and verify that new deletion is blocked until recovery.

```python
def test_replacement_failure_restores_all_originals(self):
    before = snapshot_tree(self.root)
    with self.assertRaises(CommitError):
        commit_staged(self.staged, fail_after=2)
    recover_transaction(self.staged.journal_path)
    self.assertEqual(snapshot_tree(self.root), before)

def test_pending_journal_blocks_new_delete(self):
    self.write_pending_journal()
    with self.assertRaises(PendingRecoveryError):
        ensure_no_pending_journal(self.root)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_transaction -v`

Expected: import failure because transaction functions do not exist.

- [ ] **Step 3: Implement durable journal operations**

Create a mode-0700 transaction directory and mode-0600 JSON journal. For each target, record live, backup, staged, intended action (`replace` or `delete`), original fingerprint, and state. Flush and `os.fsync` the journal file and directory after every state change. Move originals to backup using `os.replace`, then move staged replacements to live. A delete action ends after moving live to backup.

Expose these exact functions:

```python
def ensure_no_pending_journal(root: Path) -> None:
    journal = pending_journal_path(root)
    if journal.exists():
        raise PendingRecoveryError(str(journal))

def commit_staged(staged: StagedDeletion, fail_after: int | None = None) -> DeletionReport:
    journal = create_journal(staged)
    try:
        for index, entry in enumerate(journal.entries, start=1):
            apply_entry(entry)
            mark_entry_applied(journal.path, index)
            if fail_after == index:
                raise InjectedCommitFailure(index)
        report = verify_committed(staged)
        mark_journal_complete(journal.path)
        cleanup_completed_transaction(staged)
        return report
    except Exception:
        recover_transaction(journal.path)
        raise

def recover_transaction(journal_path: Path) -> None:
    journal = load_journal(journal_path)
    for entry in reversed(journal.entries):
        restore_entry(entry)
    verify_restored(journal)
    cleanup_recovered_transaction(journal)
```

Implement the referenced journal helpers in the same task. `fail_after` is test-only fault injection and must be unavailable from the public CLI. `commit_staged` must write the journal before the first live replacement and update each entry after a successful `os.replace`.

- [ ] **Step 4: Implement recovery and post-commit verification**

Recovery processes journal entries in reverse, restoring backup to live and validating original fingerprints. Successful commit validates expected new hashes and absent deletion targets before deleting backups, journal, manifest, and transaction directory. If cleanup itself fails, keep the journal in a recoverable completed state and report it.

- [ ] **Step 5: Verify GREEN**

Run: `python3 -m unittest tests.test_transaction -v`

Expected: success, injected-failure rollback, crash recovery, and pending-journal blocking tests pass.

- [ ] **Step 6: Commit the checkpoint**

```bash
git add scripts/retention/transaction.py tests/test_transaction.py
git commit -m "feat: add recoverable session deletion transactions"
```

### Task 6: Wire the four-command CLI (TDD)

**Files:**
- Create: `scripts/retention/cli.py`
- Create: `scripts/codex_session_retention.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Test root precedence (`--root`, `$CODEX_HOME`, `~/.codex`), `--days`, read-only list, plan selection, recent-session refusal, exact `DELETE`/`CLOSED`, manifest drift, pending recovery, delete report, and recover exit codes. Inject filesystem/service functions rather than mutating the real home.

```python
def test_delete_requires_both_exact_confirmations(self):
    self.assertEqual(main(["delete", "--manifest", str(self.manifest), "--confirm", "delete", "--closed-confirmation", "CLOSED"]), 2)
    self.assertEqual(main(["delete", "--manifest", str(self.manifest), "--confirm", "DELETE", "--closed-confirmation", "closed"]), 2)

def test_list_is_read_only(self):
    before = snapshot_tree(self.root)
    self.assertEqual(main(["list", "--root", str(self.root), "--days", "7"]), 0)
    self.assertEqual(snapshot_tree(self.root), before)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_cli -v`

Expected: import failure because CLI main does not exist.

- [ ] **Step 3: Implement argparse and orchestration**

Expose `list`, `plan`, `delete`, and `recover`. Return 0 on success/cancel, 2 on invalid input or safety refusal, and 1 on operational/incomplete failure. `delete` performs: pending-journal check, confirmations, manifest read/validate, staging, staged residual verification, final live fingerprint recheck, commit, post-verification, cleanup, report. It never accepts naked session IDs.

The entry file contains only:

```python
#!/usr/bin/env python3
from retention.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify GREEN and replace v1 tests/code**

Run: `python3 -m unittest tests.test_cli -v`

Expected: all command/safety tests pass.

After the v2 suite imports only the new package, delete `scripts/cleanup_codex_sessions.py` and `tests/test_cleanup_codex_sessions.py`. Remove generated `__pycache__` paths from the repository workspace.

- [ ] **Step 5: Run the complete suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: all model, discovery, display, manifest, staging, transaction, and CLI tests pass with no live-home access.

- [ ] **Step 6: Commit the checkpoint**

```bash
git add scripts tests
git commit -m "feat: expose session retention terminal commands"
```

### Task 7: Add safe installation and Skill instructions (TDD where behavioral)

**Files:**
- Create: `scripts/install.py`
- Create: `tests/test_install.py`
- Modify: `SKILL.md`
- Modify: `agents/openai.yaml`

- [ ] **Step 1: Write failing installer tests**

Install into a temporary HOME/CODEX_HOME. Assert only `SKILL.md`, `agents/openai.yaml`, implementation scripts, and package files are installed; tests, README, caches, and source docs are excluded. Assert wrapper contents use `$CODEX_HOME` fallback and are executable. Inject a replacement failure and verify the previous installation is restored.

```python
def test_installer_creates_skill_and_external_wrapper(self):
    install(repo_root=self.repo, home=self.home, codex_home=self.codex_home)
    wrapper = self.home / ".local/bin/codex-session-retention"
    self.assertTrue(wrapper.stat().st_mode & 0o111)
    self.assertIn('${CODEX_HOME:-$HOME/.codex}', wrapper.read_text(encoding="utf-8"))
    self.assertFalse((self.codex_home / "skills/codex-session-retention/tests").exists())
```

- [ ] **Step 2: Verify RED, implement installer, verify GREEN**

Run RED: `python3 -m unittest tests.test_install -v`

Implement atomic temporary-directory installation and wrapper generation:

```sh
#!/bin/sh
set -eu
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
exec python3 "$CODEX_HOME/skills/codex-session-retention/scripts/codex_session_retention.py" "$@"
```

Run GREEN: `python3 -m unittest tests.test_install -v`

Expected: clean install, upgrade, rollback, wrapper permissions, and payload filtering pass.

- [ ] **Step 3: Rewrite Skill instructions**

Use frontmatter with only `name` and a trigger-rich `description`. In the body, instruct Codex to use `list`/`plan` read-only, tell the user to exit all Codex processes, and require the user to run `delete` from an independent terminal. Explicitly prohibit Codex from running `delete` inside the current session. Include exact commands and explain `recover`.

- [ ] **Step 4: Regenerate and validate metadata**

Run:

```bash
python3 /home/devvean/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py . \
  --interface display_name='Codex Session Retention' \
  --interface short_description='Safely plan and remove complete local Codex sessions' \
  --interface default_prompt='List local Codex sessions by last activity and prepare a safe terminal-only deletion plan.'
python3 /home/devvean/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

Expected: metadata generation succeeds and the Skill validator reports valid.

- [ ] **Step 5: Commit the checkpoint**

```bash
git add SKILL.md agents/openai.yaml scripts/install.py tests/test_install.py
git commit -m "feat: install codex session retention skill safely"
```

### Task 8: Full verification and real-home read-only audit

**Files:**
- Verify only; do not modify real Codex data.

- [ ] **Step 1: Run complete tests and compile checks**

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
```

Expected: zero failures/errors and compile exit 0.

- [ ] **Step 2: Validate packaging in a temporary home**

```bash
tmp_home=$(mktemp -d)
HOME="$tmp_home" CODEX_HOME="$tmp_home/.codex" python3 scripts/install.py
HOME="$tmp_home" CODEX_HOME="$tmp_home/.codex" "$tmp_home/.local/bin/codex-session-retention" list --root "$tmp_home/.codex" --days 7
```

Expected: install succeeds; list reports zero sessions without mutation. Remove the temporary home after verification.

- [ ] **Step 3: Run read-only list against the real home**

```bash
python3 scripts/codex_session_retention.py list --root /home/devvean/.codex --days 7
```

Expected: complete recent/stale table with IDs, time sources, titles, paths/status, file/record counts, and bytes. Capture hashes/stat metadata for `state_5.sqlite`, `session_index.jsonl`, and `history.jsonl` before and after and confirm unchanged.

- [ ] **Step 4: Run a temporary manifest plan only**

Choose one stale number from the display and run `plan` with an output under `/tmp`; validate manifest mode 0600 and contents, then remove it. Do not invoke `delete` or `recover` against `/home/devvean/.codex` during development.

- [ ] **Step 5: Review requirements and repository state**

Confirm each v2 spec section maps to tests and implementation. Run a repository placeholder-marker scan over `SKILL.md`, `scripts`, and `tests` and require no matches. Run `git status --short` and verify only intended source changes remain; caches and temporary manifests must be absent.

- [ ] **Step 6: Commit the final verification adjustments if needed**

```bash
git add SKILL.md agents scripts tests docs/superpowers
git commit -m "test: verify complete codex session retention workflow"
```

## Plan self-review

- **Spec coverage:** Task 1 covers models/fixtures; Task 2 covers discovery, timestamps, ordering, display, and selection; Task 3 covers immutable IDs/paths/fingerprints and freshness; Task 4 covers JSONL, rollout, shell snapshot, every specified SQLite table, WAL backup, and residual checks; Task 5 covers journaled replacement and recovery; Task 6 covers terminal-only confirmations and all commands; Task 7 covers global Skill/wrapper installation; Task 8 covers synthetic and real-home read-only verification.
- **Placeholder scan:** No placeholder markers, vague “implement later” steps, or incomplete code snippets remain. Ellipses in tuple type annotations are Python syntax, not omitted implementation.
- **Type consistency:** `SessionRecord` feeds `build_manifest`; `Manifest.selected` feeds `stage_deletion`; `StagedDeletion.journal_path` feeds `commit_staged` and `recover_transaction`; CLI calls the exact APIs defined in Tasks 2–7.
- **Scope:** The plan intentionally does not add cloud deletion, plugin commands, cron scheduling, arbitrary text rewriting, or project-file cleanup.
