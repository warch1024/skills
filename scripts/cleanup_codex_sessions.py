"""Read-only discovery of local Codex rollout sessions."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import UUID


_UUID_RE = re.compile(
    r"(?i)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?![0-9a-f])"
)


@dataclass
class SessionInfo:
    session_id: str
    last_activity_ms: int
    title: str
    paths: list[Path]
    record_count: int
    size_bytes: int
    source: str
    stale: bool


def _canonical_uuid(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return None


def _filename_id(path: Path) -> Optional[str]:
    match = _UUID_RE.search(path.name)
    return _canonical_uuid(match.group(1)) if match else None


def _database_rows(root: Path) -> dict[str, dict[str, Any]]:
    database = root / "state_5.sqlite"
    if not database.is_file():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            cursor = connection.execute(
                "SELECT id, updated_at_ms, recency_at_ms, title, rollout_path, archived FROM threads"
            )
            for row in cursor:
                session_id = _canonical_uuid(row[0])
                if session_id is not None:
                    rows[session_id] = {
                        "updated_at_ms": row[1],
                        "recency_at_ms": row[2],
                        "title": row[3] or "",
                        "rollout_path": row[4],
                        "archived": bool(row[5]),
                    }
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return {}
    return rows


def _file_details(path: Path) -> tuple[Optional[str], int, int, Optional[str]]:
    session_id = _filename_id(path)
    count = 0
    first_user_message = None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                count += 1
                try:
                    payload = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if not isinstance(payload, dict):
                    continue
                record_type = payload.get("type")
                body = payload.get("payload")
                if session_id is None:
                    if record_type == "session_meta":
                        if isinstance(body, dict):
                            session_id = _canonical_uuid(body.get("id"))
                if first_user_message is None and record_type == "event_msg" and isinstance(body, dict):
                    if body.get("type") == "user_message" and isinstance(body.get("message"), str):
                        first_user_message = body["message"].strip() or None
                if first_user_message is None and record_type == "user_message":
                    message = payload.get("message")
                    if isinstance(message, str):
                        first_user_message = message.strip() or None
        size = path.stat().st_size
    except OSError:
        return session_id, count, 0, first_user_message
    return session_id, count, size, first_user_message


def _mtime_ms(paths: list[Path]) -> int:
    mtimes = []
    for path in paths:
        try:
            mtimes.append(path.stat().st_mtime_ns // 1_000_000)
        except OSError:
            continue
    return max(mtimes, default=0)


def _safe_path(root: Path, raw_path: Any) -> Optional[Path]:
    """Resolve a rollout path confined to the two Codex session directories."""
    if not isinstance(raw_path, (str, Path)) or not str(raw_path):
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve(strict=False)
    except (OSError, ValueError):
        return None
    if resolved.suffix.lower() != ".jsonl":
        return None
    allowed_roots = (root / "sessions", root / "archived_sessions")
    if not any(resolved.is_relative_to(directory) for directory in allowed_roots):
        return None
    return resolved


def _activity_ms(database_row: Optional[dict[str, Any]], paths: list[Path]) -> int:
    if database_row:
        updated = database_row.get("updated_at_ms")
        if isinstance(updated, (int, float)) and updated > 0:
            return int(updated)
        recency = database_row.get("recency_at_ms")
        if isinstance(recency, (int, float)) and recency > 0:
            return int(recency)
    return _mtime_ms(paths)


def discover(root: Path, now_ms: int, retention_days: int) -> list[SessionInfo]:
    """Discover and merge active and archived JSONL sessions below *root*."""
    root = Path(root).resolve()
    database_rows = _database_rows(root)
    merged: dict[str, dict[str, Any]] = {}
    scanned_paths: set[Path] = set()
    database_path_owners: dict[Path, list[str]] = {}
    for session_id, row in database_rows.items():
        path = _safe_path(root, row.get("rollout_path"))
        if path is not None:
            database_path_owners.setdefault(path, []).append(session_id)
    database_paths = {
        path: owners[0] for path, owners in database_path_owners.items() if len(owners) == 1
    }
    shared_database_paths = {
        path for path, owners in database_path_owners.items() if len(owners) > 1
    }

    # Visit active files first so merged path ordering and source are stable.
    for directory, source in ((root / "sessions", "active"), (root / "archived_sessions", "archived")):
        if not directory.is_dir():
            continue
        for raw_path in sorted(directory.rglob("*.jsonl")):
            path = _safe_path(root, raw_path)
            if path is None or path in scanned_paths:
                continue
            scanned_paths.add(path)
            # Ambiguous DB ownership is quarantined rather than attributed unsafely.
            if path in shared_database_paths:
                continue
            session_id, record_count, size_bytes, title = _file_details(path)
            # The DB identity wins whenever it names this physical rollout path.
            session_id = database_paths.get(path, session_id)
            if session_id is None:
                continue
            item = merged.setdefault(
                session_id,
                {"paths": [], "record_count": 0, "size_bytes": 0, "sources": set(), "title": None},
            )
            item["paths"].append(path)
            item["record_count"] += record_count
            item["size_bytes"] += size_bytes
            item["sources"].add(source)
            if item["title"] is None and title:
                item["title"] = title

    # Preserve thread rows even when no corresponding rollout file exists.
    for session_id, database_row in database_rows.items():
        item = merged.setdefault(
            session_id,
            {"paths": [], "record_count": 0, "size_bytes": 0, "sources": set(), "title": None},
        )
        rollout_path = database_row.get("rollout_path")
        path = _safe_path(root, rollout_path)
        if path is not None and path not in shared_database_paths:
            if path not in item["paths"]:
                item["paths"].append(path)
                if path not in scanned_paths and path.is_file():
                    _, record_count, size_bytes, title = _file_details(path)
                    item["record_count"] += record_count
                    item["size_bytes"] += size_bytes
                    if item["title"] is None and title:
                        item["title"] = title

    cutoff = now_ms - retention_days * 86_400_000
    result = []
    for session_id, item in merged.items():
        database_row = database_rows.get(session_id)
        activity = _activity_ms(database_row, item["paths"])
        if database_row is not None:
            source = "archived" if database_row.get("archived") else "active"
        else:
            source = "active" if "active" in item["sources"] else "archived"
        title = (database_row or {}).get("title", "")
        if not title:
            title = item.get("title") or "(untitled)"
        result.append(
            SessionInfo(
                session_id=session_id,
                last_activity_ms=activity,
                title=title,
                paths=item["paths"],
                record_count=item["record_count"],
                size_bytes=item["size_bytes"],
                source=source,
                stale=activity < cutoff,
            )
        )
    result.sort(key=lambda info: (-info.last_activity_ms, info.session_id))
    return result


__all__ = ["SessionInfo", "discover"]
