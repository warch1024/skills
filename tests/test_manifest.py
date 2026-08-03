import os
import tempfile
import unittest
from pathlib import Path

from scripts.retention.manifest import (
    AmbiguousOwnershipError,
    FreshSessionError,
    ManifestDriftError,
    build_manifest,
    read_manifest,
    validate_manifest,
    write_manifest,
)
from scripts.retention.model import SessionRecord


STALE_ID = "019f209c-8aea-71a0-9342-9e9a92a03286"
FRESH_ID = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"
CUTOFF_MS = 2_000_000_000_000


def make_record(root: Path, session_id: str, activity: int, ambiguous=()):
    path = root / "sessions" / f"rollout-{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"session_id": "value"}\n', encoding="utf-8")
    return SessionRecord(
        session_id=session_id,
        last_activity_ms=activity,
        activity_source="updated_at_ms",
        title=session_id,
        paths=(path.resolve(),),
        snapshot_paths=(),
        file_count=1,
        record_count=1,
        size_bytes=path.stat().st_size,
        archived=False,
        ambiguous=tuple(ambiguous),
    )


class ManifestTests(unittest.TestCase):
    def test_manifest_rejects_fresh_without_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [make_record(root, FRESH_ID, CUTOFF_MS + 1)]

            with self.assertRaises(FreshSessionError):
                build_manifest(root, records, (1,), CUTOFF_MS, allow_fresh=False)

    def test_manifest_rejects_ambiguous_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [make_record(root, STALE_ID, CUTOFF_MS - 1, ("shared path",))]

            with self.assertRaises(AmbiguousOwnershipError):
                build_manifest(root, records, (1,), CUTOFF_MS, allow_fresh=False)

    def test_manifest_is_mode_0600_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [make_record(root, STALE_ID, CUTOFF_MS - 1)]
            destination = root / "manifest.json"

            manifest = build_manifest(root, records, (1,), CUTOFF_MS, allow_fresh=False)
            written = write_manifest(manifest, destination)

            self.assertEqual(written, destination)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(read_manifest(destination), manifest)
            validate_manifest(manifest)

    def test_explicit_manifest_output_does_not_change_parent_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codex"
            root.mkdir()
            records = [make_record(root, STALE_ID, CUTOFF_MS - 1)]
            manifest = build_manifest(root, records, (1,), CUTOFF_MS, allow_fresh=False)
            output_dir = Path(tmp) / "shared"
            output_dir.mkdir(mode=0o755)
            output_dir.chmod(0o755)

            write_manifest(manifest, output_dir / "plan.manifest")

            self.assertEqual(output_dir.stat().st_mode & 0o777, 0o755)

    def test_manifest_detects_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [make_record(root, STALE_ID, CUTOFF_MS - 1)]
            manifest = build_manifest(root, records, (1,), CUTOFF_MS, allow_fresh=False)
            path = records[0].paths[0]
            path.write_text("changed\n", encoding="utf-8")

            with self.assertRaises(ManifestDriftError):
                validate_manifest(manifest)

    def test_unrelated_global_database_change_after_plan_does_not_expire_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [make_record(root, STALE_ID, CUTOFF_MS - 1)]
            database = root / "state_5.sqlite"
            database.write_bytes(b"before close")
            manifest = build_manifest(root, records, (1,), CUTOFF_MS, allow_fresh=False)

            database.write_bytes(b"after close")

            validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
