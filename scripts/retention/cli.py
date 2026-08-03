"""Terminal-only command orchestration for Codex session retention."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from .discovery import discover_sessions
from .display import SelectionError, format_session_table, parse_selection
from .manifest import (
    ManifestError,
    build_manifest,
    read_manifest,
    validate_manifest,
    write_manifest,
)
from .staging import StagingError, stage_deletion
from .transaction import (
    CommitError,
    PendingRecoveryError,
    commit_staged,
    ensure_no_pending_journal,
    recover_transaction,
)


def resolve_root(explicit: Path | None, codex_home: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    if codex_home is not None:
        return Path(codex_home).expanduser().resolve()
    configured = os.environ.get("CODEX_HOME")
    return Path(configured or (Path.home() / ".codex")).expanduser().resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-session-retention")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="read-only list of all local sessions")
    list_parser.add_argument("--root", type=Path)
    list_parser.add_argument("--days", type=int, default=7)

    plan_parser = subparsers.add_parser("plan", help="create a read-only deletion manifest")
    plan_parser.add_argument("--root", type=Path)
    plan_parser.add_argument("--days", type=int, default=7)
    plan_parser.add_argument("--select")
    plan_parser.add_argument("--allow-fresh", action="store_true")
    plan_parser.add_argument("--output", type=Path)

    delete_parser = subparsers.add_parser("delete", help="apply a manifest after Codex exits")
    delete_parser.add_argument("--manifest", type=Path, required=True)
    delete_parser.add_argument("--confirm", required=True)
    delete_parser.add_argument("--closed-confirmation", required=True)

    recover_parser = subparsers.add_parser("recover", help="restore a pending transaction journal")
    recover_parser.add_argument("--journal", type=Path, required=True)
    return parser


def _validate_days(days: int) -> None:
    if days <= 0:
        raise ManifestError("--days must be positive")


def _list_command(args: argparse.Namespace, current_ms: int) -> int:
    _validate_days(args.days)
    root = resolve_root(args.root)
    if not root.is_dir():
        raise ManifestError(f"Codex root is not a directory: {root}")
    records = discover_sessions(root, now_ms=current_ms, retention_days=args.days)
    cutoff_ms = current_ms - args.days * 86_400_000
    print(format_session_table(records, cutoff_ms=cutoff_ms, days=args.days))
    return 0


def _plan_command(args: argparse.Namespace, current_ms: int) -> int:
    _validate_days(args.days)
    root = resolve_root(args.root)
    if not root.is_dir():
        raise ManifestError(f"Codex root is not a directory: {root}")
    records = discover_sessions(root, now_ms=current_ms, retention_days=args.days)
    cutoff_ms = current_ms - args.days * 86_400_000
    print(format_session_table(records, cutoff_ms=cutoff_ms, days=args.days))
    selection_text = args.select
    if selection_text is None:
        selection_text = input("选择要删除的编号（例如 8,9-11；输入 q 取消）: ").strip()
    if selection_text.lower() in {"q", "quit"}:
        print("cancelled")
        return 0
    selected_numbers = parse_selection(selection_text, len(records))
    manifest = build_manifest(root, records, selected_numbers, cutoff_ms, args.allow_fresh)
    destination = write_manifest(manifest, args.output)
    print(f"manifest: {destination}")
    print(f"selected sessions: {', '.join(manifest.selected_ids)}")
    return 0


def _temporary_transaction_dir() -> Path:
    path = Path(tempfile.mkdtemp(prefix="codex-session-retention-"))
    path.rmdir()
    return path


def _delete_command(args: argparse.Namespace) -> int:
    if args.confirm != "DELETE" or args.closed_confirmation != "CLOSED":
        raise ManifestError("exact confirmations required: DELETE and CLOSED")
    manifest = read_manifest(args.manifest)
    validate_manifest(manifest)
    ensure_no_pending_journal(manifest.root)
    if not os.access(manifest.root, os.W_OK):
        raise ManifestError(f"Codex root is not writable: {manifest.root}")
    transaction_dir = _temporary_transaction_dir()
    try:
        staged = stage_deletion(manifest, transaction_dir)
        report = commit_staged(staged)
    except Exception:
        shutil.rmtree(transaction_dir, ignore_errors=True)
        raise
    try:
        Path(args.manifest).unlink()
    except OSError as exc:
        print(f"warning: deletion succeeded but manifest cleanup failed: {exc}", file=sys.stderr)
    print(f"deleted sessions: {report.session_count}")
    print(f"deleted files: {report.deleted_files}")
    print(f"deleted JSONL rows: {report.deleted_jsonl_rows}")
    print(f"freed bytes: {report.freed_bytes}")
    print("residual structured references: 0")
    return 0


def _recover_command(args: argparse.Namespace) -> int:
    recover_transaction(args.journal)
    print(f"recovered: {args.journal}")
    return 0


def main(
    argv: list[str] | None = None,
    *,
    clock_ms: Callable[[], int] | None = None,
) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        current_ms = clock_ms() if clock_ms is not None else int(time.time() * 1000)
        if args.command == "list":
            return _list_command(args, current_ms)
        if args.command == "plan":
            return _plan_command(args, current_ms)
        if args.command == "delete":
            return _delete_command(args)
        if args.command == "recover":
            return _recover_command(args)
        parser.error("a command is required")
    except (SelectionError, ManifestError, PendingRecoveryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (StagingError, CommitError, OSError, ValueError) as exc:
        print(f"failure: {exc}", file=sys.stderr)
        return 1


__all__ = ["main", "resolve_root"]
