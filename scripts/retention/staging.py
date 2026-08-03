"""Build deletion results on temporary copies without mutating live data."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable

from .manifest import KNOWN_DATABASES, KNOWN_ROOT_FILES, fingerprint, validate_manifest
from .model import Manifest, StagedDeletion


class StagingError(RuntimeError):
    """Raised when staged transformation or residual validation fails."""


def _stage_path(transaction_dir: Path, root: Path, live: Path) -> Path:
    relative = live.resolve(strict=False).relative_to(root.resolve())
    staged = transaction_dir / "staged" / relative
    staged.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return staged


def _rewrite_jsonl(live: Path, staged: Path, selected_ids: set[str], field: str) -> int:
    removed = 0
    with live.open("r", encoding="utf-8", errors="replace") as source, staged.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        for line in source:
            try:
                value = json.loads(line) if line.strip() else None
            except (TypeError, ValueError):
                value = None
            if isinstance(value, dict) and value.get(field) in selected_ids:
                removed += 1
                continue
            target.write(line)
    shutil.copymode(live, staged)
    return removed


def _backup_sqlite(live: Path, staged: Path) -> sqlite3.Connection:
    source = sqlite3.connect(f"file:{live}?mode=ro", uri=True, timeout=0.2)
    target = sqlite3.connect(staged, timeout=0.2)
    try:
        source.backup(target)
    finally:
        source.close()
    return target


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.Error as exc:
        raise StagingError(f"cannot inspect table {table}: {exc}") from exc
    if not rows:
        raise StagingError(f"required table is missing: {table}")
    return {row[1] for row in rows}


def _delete_rows(connection: sqlite3.Connection, table: str, column: str, ids: tuple[str, ...]) -> int:
    columns = _table_columns(connection, table)
    if column not in columns:
        raise StagingError(f"required column is missing: {table}.{column}")
    placeholders = ",".join("?" for _ in ids)
    return connection.execute(
        f'DELETE FROM "{table}" WHERE "{column}" IN ({placeholders})', ids
    ).rowcount


def _delete_state_rows(connection: sqlite3.Connection, ids: tuple[str, ...]) -> list[tuple[str, int]]:
    counts = []
    counts.append(("state_5.sqlite.thread_dynamic_tools", _delete_rows(connection, "thread_dynamic_tools", "thread_id", ids)))
    _table_columns(connection, "thread_spawn_edges")
    placeholders = ",".join("?" for _ in ids)
    counts.append(
        (
            "state_5.sqlite.thread_spawn_edges",
            connection.execute(
                f"DELETE FROM thread_spawn_edges WHERE parent_thread_id IN ({placeholders}) OR child_thread_id IN ({placeholders})",
                ids + ids,
            ).rowcount,
        )
    )
    counts.append(("state_5.sqlite.threads", _delete_rows(connection, "threads", "id", ids)))
    return counts


def _transform_database(live: Path, staged: Path, ids: tuple[str, ...]) -> list[tuple[str, int]]:
    connection = _backup_sqlite(live, staged)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        if live.name == "state_5.sqlite":
            counts = _delete_state_rows(connection, ids)
        elif live.name == "goals_1.sqlite":
            counts = [("goals_1.sqlite.thread_goals", _delete_rows(connection, "thread_goals", "thread_id", ids))]
        elif live.name == "memories_1.sqlite":
            counts = [("memories_1.sqlite.stage1_outputs", _delete_rows(connection, "stage1_outputs", "thread_id", ids))]
        elif live.name == "logs_2.sqlite":
            counts = [("logs_2.sqlite.logs", _delete_rows(connection, "logs", "thread_id", ids))]
        else:
            raise StagingError(f"unexpected database: {live.name}")
        connection.commit()
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise StagingError(f"integrity check failed for {live}")
        return counts
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        shutil.copymode(live, staged)


def _verify_jsonl_residual(path: Path, selected_ids: set[str], field: str) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                value = json.loads(line) if line.strip() else None
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict) and value.get(field) in selected_ids:
                raise StagingError(f"residual {field} reference in {path}:{line_number}")


def _verify_database_residual(path: Path, ids: tuple[str, ...]) -> None:
    connection = sqlite3.connect(path)
    try:
        if path.name == "state_5.sqlite":
            checks = (
                ("threads", "id"),
                ("thread_dynamic_tools", "thread_id"),
                ("thread_spawn_edges", "parent_thread_id"),
                ("thread_spawn_edges", "child_thread_id"),
            )
        elif path.name == "goals_1.sqlite":
            checks = (("thread_goals", "thread_id"),)
        elif path.name == "memories_1.sqlite":
            checks = (("stage1_outputs", "thread_id"),)
        elif path.name == "logs_2.sqlite":
            checks = (("logs", "thread_id"),)
        else:
            return
        for table, column in checks:
            columns = _table_columns(connection, table)
            if column not in columns:
                raise StagingError(f"required column is missing: {table}.{column}")
            placeholders = ",".join("?" for _ in ids)
            if connection.execute(
                f'SELECT 1 FROM "{table}" WHERE "{column}" IN ({placeholders}) LIMIT 1', ids
            ).fetchone():
                raise StagingError(f"residual database reference in {path}: {table}.{column}")
    finally:
        connection.close()


def _selected_paths(manifest: Manifest) -> tuple[Path, ...]:
    paths = []
    for item in manifest.selected:
        paths.extend(item.rollout_paths)
        paths.extend(item.snapshot_paths)
    return tuple(dict.fromkeys(path.resolve(strict=False) for path in paths))


def _global_live_paths(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for name in KNOWN_ROOT_FILES:
        path = root / name
        if path.exists() and path.is_file():
            paths.append(path.resolve())
        if name in KNOWN_DATABASES:
            for suffix in ("-wal", "-shm"):
                sidecar = root / f"{name}{suffix}"
                if sidecar.exists() and sidecar.is_file():
                    paths.append(sidecar.resolve())
    return tuple(paths)


def stage_deletion(manifest: Manifest, transaction_dir: Path) -> StagedDeletion:
    validate_manifest(manifest)
    transaction_dir = Path(transaction_dir).resolve()
    if transaction_dir.exists():
        raise StagingError(f"transaction directory already exists: {transaction_dir}")
    transaction_dir.mkdir(mode=0o700, parents=True)
    root = manifest.root.resolve()
    ids = manifest.selected_ids
    selected_ids = set(ids)
    global_fingerprints = tuple(fingerprint(path) for path in _global_live_paths(root))
    replacements: list[tuple[Path, Path]] = []
    jsonl_counts: list[tuple[str, int]] = []
    sqlite_counts: list[tuple[str, int]] = []

    for expected in global_fingerprints:
        live = expected.path.resolve(strict=False)
        if not expected.exists or not live.exists():
            continue
        if live.name in ("session_index.jsonl", "history.jsonl"):
            staged = _stage_path(transaction_dir, root, live)
            field = "id" if live.name == "session_index.jsonl" else "session_id"
            removed = _rewrite_jsonl(live, staged, selected_ids, field)
            replacements.append((live, staged))
            jsonl_counts.append((live.name, removed))
        elif live.name in KNOWN_DATABASES and live.suffix == ".sqlite":
            staged = _stage_path(transaction_dir, root, live)
            sqlite_counts.extend(_transform_database(live, staged, ids))
            replacements.append((live, staged))

    sidecars = tuple(
        expected.path.resolve()
        for expected in global_fingerprints
        if expected.exists
        and expected.path.name.endswith(("-wal", "-shm"))
        and expected.path.exists()
    )
    deletion_paths = tuple(
        dict.fromkeys(
            path
            for path in _selected_paths(manifest) + sidecars
            if path.exists() and path.is_file()
        )
    )
    for live, _ in replacements:
        if live.name in KNOWN_DATABASES and live.suffix == ".sqlite":
            _verify_database_residual(dict(replacements)[live], ids)
        elif live.name == "session_index.jsonl":
            _verify_jsonl_residual(dict(replacements)[live], selected_ids, "id")
        elif live.name == "history.jsonl":
            _verify_jsonl_residual(dict(replacements)[live], selected_ids, "session_id")

    freed_bytes = sum(path.stat().st_size for path in deletion_paths)
    source_fingerprints = tuple(
        dict.fromkeys(manifest.fingerprints + global_fingerprints)
    )
    for expected in source_fingerprints:
        if fingerprint(expected.path) != expected:
            raise StagingError(f"source changed while staging: {expected.path}")
    journal_path = root / ".codex-session-retention.journal.json"
    return StagedDeletion(
        root=root,
        transaction_dir=transaction_dir,
        session_count=len(manifest.selected),
        source_fingerprints=source_fingerprints,
        replacements=tuple(replacements),
        deletion_paths=deletion_paths,
        jsonl_rows=tuple(jsonl_counts),
        sqlite_rows=tuple(sqlite_counts),
        freed_bytes=freed_bytes,
        journal_path=journal_path,
    )


__all__ = ["StagingError", "stage_deletion"]
