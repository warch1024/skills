"""Synthetic Codex-home builders used by the retention tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable


DAY_MS = 86_400_000
NOW_MS = 2_000_000_000_000


def write_jsonl(path: Path, records: Iterable[object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def write_rollout(
    root: Path,
    session_id: str,
    *,
    archived: bool = False,
    timestamp: str = "2033-05-17T03:33:20Z",
    title: str | None = None,
    filename_id: str | None = None,
) -> Path:
    directory = root / ("archived_sessions" if archived else "sessions/2033/05/17")
    path = directory / f"rollout-2033-05-17T03-33-20-{filename_id or session_id}.jsonl"
    records: list[object] = [
        {"timestamp": timestamp, "type": "session_meta", "payload": {"id": session_id}}
    ]
    if title is not None:
        records.append(
            {
                "timestamp": timestamp,
                "type": "event_msg",
                "payload": {"type": "user_message", "message": title},
            }
        )
    return write_jsonl(path, records)


def create_state_db(
    root: Path,
    threads: Iterable[tuple[str, int, int, str, str, int]],
    *,
    dynamic_tools: Iterable[tuple[str, int, str]] = (),
    spawn_edges: Iterable[tuple[str, str, str]] = (),
) -> Path:
    path = root / "state_5.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            updated_at_ms INTEGER,
            recency_at_ms INTEGER,
            title TEXT NOT NULL,
            rollout_path TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE thread_dynamic_tools (
            thread_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            name TEXT NOT NULL,
            PRIMARY KEY(thread_id, position)
        );
        CREATE TABLE thread_spawn_edges (
            parent_thread_id TEXT NOT NULL,
            child_thread_id TEXT NOT NULL PRIMARY KEY,
            status TEXT NOT NULL
        );
        """
    )
    connection.executemany("INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)", threads)
    connection.executemany("INSERT INTO thread_dynamic_tools VALUES (?, ?, ?)", dynamic_tools)
    connection.executemany("INSERT INTO thread_spawn_edges VALUES (?, ?, ?)", spawn_edges)
    connection.commit()
    connection.close()
    return path


def create_goals_db(root: Path, rows: Iterable[tuple[str, str, str]]) -> Path:
    path = root / "goals_1.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE thread_goals (thread_id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, status TEXT NOT NULL)"
    )
    connection.executemany("INSERT INTO thread_goals VALUES (?, ?, ?)", rows)
    connection.commit()
    connection.close()
    return path


def create_memories_db(root: Path, rows: Iterable[tuple[str, str]]) -> Path:
    path = root / "memories_1.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE stage1_outputs (thread_id TEXT PRIMARY KEY, rollout_slug TEXT NOT NULL)"
    )
    connection.executemany("INSERT INTO stage1_outputs VALUES (?, ?)", rows)
    connection.commit()
    connection.close()
    return path


def create_logs_db(root: Path, rows: Iterable[tuple[int, str | None, str]]) -> Path:
    path = root / "logs_2.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE logs (id INTEGER PRIMARY KEY, thread_id TEXT, feedback_log_body TEXT NOT NULL)"
    )
    connection.executemany("INSERT INTO logs VALUES (?, ?, ?)", rows)
    connection.commit()
    connection.close()
    return path


def write_shell_snapshot(
    root: Path, filename_id: str, content_id: str, serial: str = "1234567890"
) -> Path:
    path = root / "shell_snapshots" / f"{filename_id}.{serial}.sh"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"export CODEX_THREAD_ID='{content_id}'\n", encoding="utf-8")
    return path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
