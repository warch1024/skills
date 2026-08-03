"""Immutable data models shared by discovery, planning, and deletion stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "exists": self.exists,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileFingerprint":
        return cls(
            path=Path(data["path"]),
            exists=bool(data["exists"]),
            size=int(data["size"]),
            mtime_ns=int(data["mtime_ns"]),
            sha256=str(data["sha256"]),
        )


@dataclass(frozen=True)
class ManifestSession:
    session_id: str
    last_activity_ms: int
    rollout_paths: tuple[Path, ...]
    snapshot_paths: tuple[Path, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "last_activity_ms": self.last_activity_ms,
            "rollout_paths": [str(path) for path in self.rollout_paths],
            "snapshot_paths": [str(path) for path in self.snapshot_paths],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestSession":
        return cls(
            session_id=str(data["session_id"]),
            last_activity_ms=int(data["last_activity_ms"]),
            rollout_paths=tuple(Path(path) for path in data.get("rollout_paths", [])),
            snapshot_paths=tuple(Path(path) for path in data.get("snapshot_paths", [])),
        )


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "root": str(self.root),
            "created_at_ms": self.created_at_ms,
            "cutoff_ms": self.cutoff_ms,
            "selected": [item.to_dict() for item in self.selected],
            "fingerprints": [item.to_dict() for item in self.fingerprints],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        return cls(
            version=int(data["version"]),
            root=Path(data["root"]),
            created_at_ms=int(data["created_at_ms"]),
            cutoff_ms=int(data["cutoff_ms"]),
            selected=tuple(ManifestSession.from_dict(item) for item in data["selected"]),
            fingerprints=tuple(FileFingerprint.from_dict(item) for item in data["fingerprints"]),
        )


@dataclass(frozen=True)
class DeletionReport:
    session_count: int
    deleted_files: int
    deleted_jsonl_rows: int
    deleted_sqlite_rows: tuple[tuple[str, int], ...]
    freed_bytes: int
    residual_references: tuple[str, ...]


@dataclass(frozen=True)
class StagedDeletion:
    root: Path
    transaction_dir: Path
    session_count: int
    source_fingerprints: tuple[FileFingerprint, ...]
    replacements: tuple[tuple[Path, Path], ...]
    deletion_paths: tuple[Path, ...]
    jsonl_rows: tuple[tuple[str, int], ...]
    sqlite_rows: tuple[tuple[str, int], ...]
    freed_bytes: int
    journal_path: Path
