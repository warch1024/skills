import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.retention.model import (
    FileFingerprint,
    Manifest,
    ManifestSession,
    SessionRecord,
)


SESSION_ID = "019f209c-8aea-71a0-9342-9e9a92a03286"


class SessionRecordTests(unittest.TestCase):
    def test_stale_boundary_is_strict(self):
        cutoff_ms = 2_000_000_000_000
        record = SessionRecord(
            session_id=SESSION_ID,
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

        self.assertFalse(record.is_stale(cutoff_ms))
        self.assertTrue(record.is_stale(cutoff_ms + 1))

    def test_model_is_immutable(self):
        record = SessionRecord(
            session_id=SESSION_ID,
            last_activity_ms=1,
            activity_source="mtime",
            title="Immutable",
            paths=(),
            snapshot_paths=(),
            file_count=0,
            record_count=0,
            size_bytes=0,
            archived=False,
            ambiguous=(),
        )

        with self.assertRaises(FrozenInstanceError):
            record.title = "Changed"


class ManifestModelTests(unittest.TestCase):
    def test_manifest_round_trip_preserves_paths_and_selected_ids(self):
        root = Path("/tmp/codex")
        selected = ManifestSession(
            session_id=SESSION_ID,
            last_activity_ms=1234,
            rollout_paths=(root / "sessions/rollout.jsonl",),
            snapshot_paths=(root / "shell_snapshots/snapshot.sh",),
        )
        fingerprint = FileFingerprint(
            path=root / "history.jsonl",
            exists=True,
            size=15,
            mtime_ns=20,
            sha256="abc123",
        )
        manifest = Manifest(
            version=1,
            root=root,
            created_at_ms=1000,
            cutoff_ms=500,
            selected=(selected,),
            fingerprints=(fingerprint,),
        )

        restored = Manifest.from_dict(manifest.to_dict())

        self.assertEqual(restored, manifest)
        self.assertEqual(restored.selected_ids, (SESSION_ID,))


if __name__ == "__main__":
    unittest.main()
