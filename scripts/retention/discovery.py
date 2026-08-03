"""Read-only discovery of local Codex sessions and their safe associations."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from .model import SessionRecord


DAY_MS = 86_400_000
UUID_RE = re.compile(
    r"(?i)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?![0-9a-f])"
)
SNAPSHOT_ID_RE = re.compile(r"CODEX_THREAD_ID(?:=|\s+)(?:['\"])?([0-9a-f-]{36})", re.I)


@dataclass
class _FileDetails:
    file_id: str | None
    record_count: int
    size_bytes: int
    title: str | None
    latest_timestamp_ms: int
    ambiguity: str | None


def _canonical_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return None


def _timestamp_ms(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        number = int(value)
        return number if number >= 1_000_000_000_000 else number * 1000
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return _timestamp_ms(float(text))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _filename_id(path: Path) -> str | None:
    match = UUID_RE.search(path.name)
    return _canonical_id(match.group(1)) if match else None


def _safe_rollout_path(root: Path, raw_path: Any) -> Path | None:
    if not isinstance(raw_path, (str, Path)) or not str(raw_path):
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, ValueError):
        return None
    if resolved.suffix.lower() != ".jsonl":
        return None
    allowed = (root / "sessions").resolve(), (root / "archived_sessions").resolve()
    if not any(resolved == directory or directory in resolved.parents for directory in allowed):
        return None
    return resolved


def _database_rows(root: Path) -> dict[str, dict[str, Any]]:
    database = root / "state_5.sqlite"
    if not database.is_file():
        return {}
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                "SELECT id, updated_at_ms, recency_at_ms, title, rollout_path, archived FROM threads"
            )
            return {
                session_id: {
                    "updated_at_ms": row[1],
                    "recency_at_ms": row[2],
                    "title": row[3] or "",
                    "rollout_path": row[4],
                    "archived": bool(row[5]),
                }
                for row in rows
                if (session_id := _canonical_id(row[0])) is not None
            }
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return {}


def _file_details(path: Path) -> _FileDetails:
    filename_id = _filename_id(path)
    metadata_id: str | None = None
    title: str | None = None
    latest_timestamp_ms = 0
    record_count = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record_count += 1
                try:
                    payload = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if not isinstance(payload, dict):
                    continue
                for key in ("timestamp", "ts", "created_at", "updated_at"):
                    timestamp = _timestamp_ms(payload.get(key))
                    if timestamp is not None:
                        latest_timestamp_ms = max(latest_timestamp_ms, timestamp)
                if payload.get("type") == "session_meta":
                    body = payload.get("payload")
                    if isinstance(body, dict):
                        metadata_id = _canonical_id(body.get("id")) or metadata_id
                body = payload.get("payload")
                if (
                    title is None
                    and payload.get("type") == "event_msg"
                    and isinstance(body, dict)
                    and body.get("type") == "user_message"
                    and isinstance(body.get("message"), str)
                ):
                    title = body["message"].strip() or None
        size_bytes = path.stat().st_size
    except OSError:
        return _FileDetails(filename_id, record_count, 0, title, latest_timestamp_ms, None)

    if filename_id and metadata_id and filename_id != metadata_id:
        return _FileDetails(
            None,
            record_count,
            size_bytes,
            title,
            latest_timestamp_ms,
            "rollout filename/session_meta identity mismatch",
        )
    return _FileDetails(
        metadata_id or filename_id,
        record_count,
        size_bytes,
        title,
        latest_timestamp_ms,
        None,
    )


def _mtime_ms(paths: tuple[Path, ...]) -> int:
    values = []
    for path in paths:
        try:
            values.append(path.stat().st_mtime_ns // 1_000_000)
        except OSError:
            continue
    return max(values, default=0)


def _snapshot_identity(path: Path) -> tuple[str | None, str | None]:
    filename_id = _filename_id(path)
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return filename_id, None
    match = SNAPSHOT_ID_RE.search(content)
    return filename_id, _canonical_id(match.group(1)) if match else None


def discover_sessions(root: Path, now_ms: int, retention_days: int) -> list[SessionRecord]:
    root = Path(root).resolve()
    database_rows = _database_rows(root)
    merged: dict[str, dict[str, Any]] = {
        session_id: {
            "paths": [],
            "snapshots": [],
            "records": 0,
            "bytes": 0,
            "title": None,
            "timestamps": [],
            "sources": set(),
            "ambiguous": [],
        }
        for session_id in database_rows
    }

    db_owners: dict[Path, list[str]] = {}
    for session_id, row in database_rows.items():
        path = _safe_rollout_path(root, row.get("rollout_path"))
        if path is not None:
            db_owners.setdefault(path, []).append(session_id)
    shared_paths = {path for path, owners in db_owners.items() if len(owners) > 1}
    unique_owner = {
        path: owners[0] for path, owners in db_owners.items() if len(owners) == 1
    }

    for directory, source in (
        (root / "sessions", "active"),
        (root / "archived_sessions", "archived"),
    ):
        if not directory.is_dir():
            continue
        for raw_path in sorted(directory.rglob("*.jsonl")):
            path = _safe_rollout_path(root, raw_path)
            if path is None or path in shared_paths:
                continue
            details = _file_details(path)
            owner = unique_owner.get(path)
            if owner is not None and details.file_id not in (None, owner):
                for session_id in (owner, details.file_id):
                    if session_id in merged:
                        merged[session_id]["ambiguous"].append(
                            "database/rollout identity mismatch"
                        )
                continue
            session_id = owner or details.file_id
            if session_id is None:
                continue
            item = merged.setdefault(
                session_id,
                {
                    "paths": [],
                    "snapshots": [],
                    "records": 0,
                    "bytes": 0,
                    "title": None,
                    "timestamps": [],
                    "sources": set(),
                    "ambiguous": [],
                },
            )
            if details.ambiguity:
                item["ambiguous"].append(details.ambiguity)
                continue
            item["paths"].append(path)
            item["records"] += details.record_count
            item["bytes"] += details.size_bytes
            item["sources"].add(source)
            if details.title and item["title"] is None:
                item["title"] = details.title
            if details.latest_timestamp_ms:
                item["timestamps"].append(details.latest_timestamp_ms)

    for path, owners in db_owners.items():
        if path in shared_paths:
            for session_id in owners:
                merged[session_id]["ambiguous"].append("shared rollout path")
            continue
        owner = owners[0]
        if path in merged[owner]["paths"] or not path.is_file():
            continue
        details = _file_details(path)
        if details.ambiguity:
            merged[owner]["ambiguous"].append(details.ambiguity)
            continue
        merged[owner]["paths"].append(path)
        merged[owner]["records"] += details.record_count
        merged[owner]["bytes"] += details.size_bytes
        if details.title and merged[owner]["title"] is None:
            merged[owner]["title"] = details.title
        if details.latest_timestamp_ms:
            merged[owner]["timestamps"].append(details.latest_timestamp_ms)

    known_ids = set(merged)
    snapshot_dir = root / "shell_snapshots"
    if snapshot_dir.is_dir():
        for path in sorted(snapshot_dir.iterdir()):
            if not path.is_file():
                continue
            filename_id, content_id = _snapshot_identity(path)
            if filename_id == content_id and filename_id in known_ids:
                merged[filename_id]["snapshots"].append(path.resolve())
            else:
                for session_id in {filename_id, content_id} & known_ids:
                    merged[session_id]["ambiguous"].append(
                        "shell snapshot identity mismatch"
                    )

    cutoff_ms = now_ms - retention_days * DAY_MS
    records: list[SessionRecord] = []
    for session_id, item in merged.items():
        row = database_rows.get(session_id)
        paths = tuple(dict.fromkeys(item["paths"]))
        updated = row.get("updated_at_ms") if row else None
        recency = row.get("recency_at_ms") if row else None
        if isinstance(updated, (int, float)) and updated > 0:
            activity_ms, source = int(updated), "updated_at_ms"
        elif isinstance(recency, (int, float)) and recency > 0:
            activity_ms, source = int(recency), "recency_at_ms"
        elif item["timestamps"]:
            activity_ms, source = max(item["timestamps"]), "rollout_timestamp"
        else:
            activity_ms, source = _mtime_ms(paths), "mtime"
        records.append(
            SessionRecord(
                session_id=session_id,
                last_activity_ms=activity_ms,
                activity_source=source,
                title=(row or {}).get("title") or item["title"] or "(untitled)",
                paths=paths,
                snapshot_paths=tuple(dict.fromkeys(item["snapshots"])),
                file_count=len(paths),
                record_count=item["records"],
                size_bytes=item["bytes"] + sum(path.stat().st_size for path in item["snapshots"] if path.exists()),
                archived=bool((row or {}).get("archived")) or "archived" in item["sources"],
                ambiguous=tuple(dict.fromkeys(item["ambiguous"])),
            )
        )
    records.sort(key=lambda record: (-record.last_activity_ms, record.session_id))
    return records


__all__ = ["discover_sessions"]
