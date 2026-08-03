"""Journaled live replacement and recovery for staged retention deletions."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .manifest import fingerprint
from .model import DeletionReport, StagedDeletion


class TransactionError(RuntimeError):
    """Base transaction error."""


class PendingRecoveryError(TransactionError):
    pass


class CommitError(TransactionError):
    pass


class InjectedCommitFailure(CommitError):
    pass


def pending_journal_path(root: Path) -> Path:
    return Path(root).resolve() / ".codex-session-retention.journal.json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)


def ensure_no_pending_journal(root: Path) -> None:
    journal = pending_journal_path(root)
    if journal.exists():
        raise PendingRecoveryError(str(journal))


def _relative_backup_path(staged: StagedDeletion, live: Path) -> Path:
    return staged.transaction_dir / "backup" / live.resolve().relative_to(staged.root.resolve())


def _create_journal(staged: StagedDeletion) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    replacement_lives = {live.resolve() for live, _ in staged.replacements}
    for live, staged_path in staged.replacements:
        backup = _relative_backup_path(staged, live)
        backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        entries.append(
            {
                "live": str(live.resolve()),
                "backup": str(backup),
                "staged": str(staged_path.resolve()),
                "action": "replace",
                "state": "pending",
            }
        )
    for live in staged.deletion_paths:
        live = live.resolve()
        if live in replacement_lives:
            continue
        backup = _relative_backup_path(staged, live)
        backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        entries.append(
            {
                "live": str(live),
                "backup": str(backup),
                "staged": "",
                "action": "delete",
                "state": "pending",
            }
        )
    journal = {
        "version": 1,
        "root": str(staged.root),
        "transaction_dir": str(staged.transaction_dir),
        "entries": entries,
        "state": "pending",
    }
    _write_json(staged.journal_path, journal)
    return journal


def _load_journal(path: Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        journal = json.load(handle)
    if journal.get("version") != 1 or not isinstance(journal.get("entries"), list):
        raise TransactionError(f"invalid journal: {path}")
    return journal


def _mark_entry(path: Path, journal: dict[str, Any], index: int, state: str) -> None:
    journal["entries"][index]["state"] = state
    _write_json(path, journal)


def _apply_entry(
    entry: dict[str, Any], journal_path: Path, journal: dict[str, Any], index: int
) -> None:
    live = Path(entry["live"])
    backup = Path(entry["backup"])
    backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if live.exists():
        os.replace(live, backup)
    entry["state"] = "backed_up"
    _mark_entry(journal_path, journal, index, "backed_up")
    if entry["action"] == "replace":
        staged = Path(entry["staged"])
        if not staged.exists():
            raise CommitError(f"staged file is missing: {staged}")
        live.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(staged, live)
    entry["state"] = "applied"
    _mark_entry(journal_path, journal, index, "applied")


def _restore_entry(entry: dict[str, Any]) -> None:
    live = Path(entry["live"])
    backup = Path(entry["backup"])
    if live.exists():
        live.unlink()
    if backup.exists():
        live.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(backup, live)


def _cleanup_transaction(journal_path: Path, transaction_dir: Path) -> None:
    try:
        journal_path.unlink()
    except FileNotFoundError:
        pass
    shutil.rmtree(transaction_dir, ignore_errors=True)


def recover_transaction(journal_path: Path) -> None:
    journal_path = Path(journal_path).resolve()
    if not journal_path.exists():
        return
    journal = _load_journal(journal_path)
    try:
        for entry in reversed(journal["entries"]):
            if entry.get("state") in {"backed_up", "applied"}:
                _restore_entry(entry)
        transaction_dir = Path(journal["transaction_dir"])
        _cleanup_transaction(journal_path, transaction_dir)
    except Exception as exc:
        raise TransactionError(f"recovery failed for {journal_path}: {exc}") from exc


def _verify_commit(staged: StagedDeletion) -> None:
    for path in staged.deletion_paths:
        if path.exists():
            raise CommitError(f"deletion target remains: {path}")
    for live, _ in staged.replacements:
        if not live.exists():
            raise CommitError(f"replacement is missing: {live}")


def _verify_sources_unchanged(staged: StagedDeletion) -> None:
    for expected in staged.source_fingerprints:
        if fingerprint(expected.path) != expected:
            raise CommitError(f"source changed after staging: {expected.path}")


def commit_staged(staged: StagedDeletion, fail_after: int | None = None) -> DeletionReport:
    ensure_no_pending_journal(staged.root)
    _verify_sources_unchanged(staged)
    journal = _create_journal(staged)
    journal_path = staged.journal_path
    try:
        for index, entry in enumerate(journal["entries"]):
            _apply_entry(entry, journal_path, journal, index)
            if fail_after is not None and index + 1 == fail_after:
                raise InjectedCommitFailure(index + 1)
        _verify_commit(staged)
        journal["state"] = "complete"
        _write_json(journal_path, journal)
        report = DeletionReport(
            session_count=staged.session_count,
            deleted_files=len(staged.deletion_paths),
            deleted_jsonl_rows=sum(count for _, count in staged.jsonl_rows),
            deleted_sqlite_rows=staged.sqlite_rows,
            freed_bytes=staged.freed_bytes,
            residual_references=(),
        )
        _cleanup_transaction(journal_path, staged.transaction_dir)
        return report
    except InjectedCommitFailure as exc:
        try:
            recover_transaction(journal_path)
        except Exception as recovery_error:
            raise CommitError(f"commit failed and recovery failed: {recovery_error}") from exc
        raise
    except Exception as exc:
        try:
            recover_transaction(journal_path)
        except Exception as recovery_error:
            raise CommitError(f"commit failed and recovery failed: {recovery_error}") from exc
        raise CommitError(str(exc)) from exc


__all__ = [
    "CommitError",
    "InjectedCommitFailure",
    "PendingRecoveryError",
    "TransactionError",
    "commit_staged",
    "ensure_no_pending_journal",
    "pending_journal_path",
    "recover_transaction",
]
