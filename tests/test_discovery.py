import tempfile
import unittest
from pathlib import Path

from scripts.retention.discovery import discover_sessions

from tests.fixtures import DAY_MS, NOW_MS, create_state_db, write_rollout, write_shell_snapshot


RECENT_DB_ID = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"
RECENT_EVENT_ID = "019f4aed-051d-71e2-80f1-af6f1d05af87"
STALE_ID = "019f209c-8aea-71a0-9342-9e9a92a03286"
SNAPSHOT_ID = "019f6511-86fc-7b60-9204-3e5f3ad94988"


class DiscoveryTests(unittest.TestCase):
    def test_activity_priority_and_full_ordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recent_db = write_rollout(root, RECENT_DB_ID, title="DB title")
            recent_event = write_rollout(
                root,
                RECENT_EVENT_ID,
                timestamp="2033-05-17T03:33:19Z",
                title="Event title",
            )
            stale = write_rollout(root, STALE_ID, title="Stale title")
            create_state_db(
                root,
                [
                    (RECENT_DB_ID, NOW_MS - DAY_MS, 0, "DB title", str(recent_db), 0),
                    (STALE_ID, NOW_MS - 10 * DAY_MS, 0, "Stale title", str(stale), 1),
                ],
            )
            recent_event.touch()

            records = discover_sessions(root, now_ms=NOW_MS, retention_days=7)

            self.assertEqual(
                [record.session_id for record in records],
                [RECENT_DB_ID, RECENT_EVENT_ID, STALE_ID],
            )
            self.assertEqual(records[0].activity_source, "updated_at_ms")
            self.assertEqual(records[1].activity_source, "rollout_timestamp")
            self.assertEqual(records[2].activity_source, "updated_at_ms")
            self.assertFalse(records[0].is_stale(NOW_MS - 7 * DAY_MS))
            self.assertTrue(records[2].is_stale(NOW_MS - 7 * DAY_MS))

    def test_database_only_row_is_listed_with_missing_rollout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "archived_sessions" / "rollout-missing.jsonl"
            create_state_db(
                root,
                [(STALE_ID, NOW_MS - 10 * DAY_MS, 0, "Missing", str(missing), 1)],
            )

            records = discover_sessions(root, now_ms=NOW_MS, retention_days=7)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].paths, ())
            self.assertEqual(records[0].file_count, 0)
            self.assertEqual(records[0].title, "Missing")
            self.assertTrue(records[0].archived)

    def test_snapshot_requires_filename_and_content_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rollout = write_rollout(root, SNAPSHOT_ID, title="Snapshot")
            verified = write_shell_snapshot(root, SNAPSHOT_ID, SNAPSHOT_ID, "1")
            mismatched = write_shell_snapshot(root, SNAPSHOT_ID, STALE_ID, "2")
            unrelated = write_shell_snapshot(root, STALE_ID, SNAPSHOT_ID, "3")

            records = discover_sessions(root, now_ms=NOW_MS, retention_days=7)
            target = next(record for record in records if record.session_id == SNAPSHOT_ID)

            self.assertEqual(target.snapshot_paths, (verified,))
            self.assertTrue(any("shell snapshot identity mismatch" in item for item in target.ambiguous))
            self.assertNotIn(mismatched, target.snapshot_paths)
            self.assertNotIn(unrelated, target.snapshot_paths)
            self.assertIn(rollout, target.paths)

    def test_shared_rollout_path_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = write_rollout(root, RECENT_DB_ID)
            create_state_db(
                root,
                [
                    (RECENT_DB_ID, NOW_MS - DAY_MS, 0, "First", str(shared), 0),
                    (STALE_ID, NOW_MS - 10 * DAY_MS, 0, "Second", str(shared), 0),
                ],
            )

            records = discover_sessions(root, now_ms=NOW_MS, retention_days=7)

            self.assertEqual(records[0].paths, ())
            self.assertTrue(records[0].ambiguous)
            self.assertEqual(records[1].paths, ())
            self.assertTrue(records[1].ambiguous)


if __name__ == "__main__":
    unittest.main()
