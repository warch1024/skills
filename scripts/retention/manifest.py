"""Immutable selection manifests and live-file drift protection."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

from .model import FileFingerprint, Manifest, ManifestSession, SessionRecord


class ManifestError(ValueError):
    """Base class for invalid or unsafe manifests."""


class FreshSessionError(ManifestError):
    pass


class AmbiguousOwnershipError(ManifestError):
    pass


class ManifestDriftError(ManifestError):
    pass


class ManifestVersionError(ManifestError):
    pass


KNOWN_ROOT_FILES = (
    "session_index.jsonl",
    "history.jsonl",
    "state_5.sqlite",
    "goals_1.sqlite",
    "memories_1.sqlite",
    "logs_2.sqlite",
)
KNOWN_DATABASES = {
    "state_5.sqlite",
    "goals_1.sqlite",
    "memories_1.sqlite",
    "logs_2.sqlite",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def default_manifest_path() -> Path:
    directory = Path(tempfile.gettempdir()) / "codex-session-retention"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory / f"plan-{uuid.uuid4().hex}.manifest"


def fingerprint(path: Path) -> FileFingerprint:
    path = path.resolve(strict=False)
    if not path.exists():
        return FileFingerprint(path, False, 0, 0, "")
    if not path.is_file():
        raise ManifestError(f"not a regular file: {path}")
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return FileFingerprint(path, True, stat.st_size, stat.st_mtime_ns, digest.hexdigest())


def _is_under(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def _is_allowed_target(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve(strict=False)
    if path.parent == root and path.name in KNOWN_ROOT_FILES:
        return True
    if path.parent == root and any(
        path.name == f"{database}{suffix}"
        for database in KNOWN_DATABASES
        for suffix in ("-wal", "-shm")
    ):
        return True
    return any(
        _is_under(path, (root / directory).resolve())
        for directory in ("sessions", "archived_sessions", "shell_snapshots")
    )


def collect_manifest_paths(root: Path, selected: tuple[ManifestSession, ...]) -> tuple[Path, ...]:
    root = root.resolve()
    paths: list[Path] = []
    for session in selected:
        paths.extend(path.resolve(strict=False) for path in session.rollout_paths)
        paths.extend(path.resolve(strict=False) for path in session.snapshot_paths)
    unique = tuple(dict.fromkeys(paths))
    invalid = [path for path in unique if not _is_allowed_target(root, path)]
    if invalid:
        raise ManifestError(f"manifest path outside known targets: {invalid[0]}")
    return unique


def build_manifest(
    root: Path,
    records: list[SessionRecord],
    selected_numbers: tuple[int, ...],
    cutoff_ms: int,
    allow_fresh: bool,
) -> Manifest:
    if not selected_numbers:
        raise ManifestError("no sessions selected")
    if any(number < 1 or number > len(records) for number in selected_numbers):
        raise ManifestError("selection number is out of range")
    selected_records = tuple(records[number - 1] for number in selected_numbers)
    if not allow_fresh and any(not item.is_stale(cutoff_ms) for item in selected_records):
        raise FreshSessionError("recent sessions require --allow-fresh")
    if any(item.ambiguous for item in selected_records):
        raise AmbiguousOwnershipError("selected session has ambiguous ownership")
    selected = tuple(
        ManifestSession(
            session_id=item.session_id,
            last_activity_ms=item.last_activity_ms,
            rollout_paths=item.paths,
            snapshot_paths=item.snapshot_paths,
        )
        for item in selected_records
    )
    root = root.resolve()
    paths = collect_manifest_paths(root, selected)
    return Manifest(
        version=1,
        root=root,
        created_at_ms=now_ms(),
        cutoff_ms=cutoff_ms,
        selected=selected,
        fingerprints=tuple(fingerprint(path) for path in paths),
    )


def write_manifest(manifest: Manifest, output: Path | None = None) -> Path:
    destination = (output or default_manifest_path()).resolve()
    if not destination.parent.exists():
        destination.parent.mkdir(mode=0o700, parents=True)
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest.to_dict(), handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            destination.unlink()
        except OSError:
            pass
        raise
    os.chmod(destination, 0o600)
    return destination


def read_manifest(path: Path) -> Manifest:
    with Path(path).open(encoding="utf-8") as handle:
        return Manifest.from_dict(json.load(handle))


def validate_manifest(manifest: Manifest) -> None:
    if manifest.version != 1:
        raise ManifestVersionError(manifest.version)
    root = manifest.root.resolve()
    if tuple(dict.fromkeys(manifest.selected_ids)) != manifest.selected_ids:
        raise ManifestError("manifest contains duplicate session IDs")
    for session in manifest.selected:
        if not session.session_id:
            raise ManifestError("manifest contains an empty session ID")
        for path in session.rollout_paths + session.snapshot_paths:
            if not _is_allowed_target(root, path):
                raise ManifestError(f"session path is not an allowed target: {path}")
    for expected in manifest.fingerprints:
        current = fingerprint(expected.path)
        if current != expected:
            raise ManifestDriftError(str(expected.path))


__all__ = [
    "AmbiguousOwnershipError",
    "FreshSessionError",
    "ManifestDriftError",
    "ManifestError",
    "ManifestVersionError",
    "build_manifest",
    "collect_manifest_paths",
    "default_manifest_path",
    "fingerprint",
    "now_ms",
    "read_manifest",
    "validate_manifest",
    "write_manifest",
]
