import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from scripts.cleanup_codex_sessions import discover


NOW_MS = 2_000_000_000_000
DAY_MS = 86_400_000


def write_rollout(path: Path, session_id: str, *records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"timestamp": "2026-01-01T00:00:00Z", "type": "session_meta", "payload": {"id": session_id}}]
    payload.extend(records)
    path.write_text("".join(json.dumps(record) + "\n" for record in payload), encoding="utf-8")


def write_threads_db(root: Path, rows: list[tuple]) -> None:
    db = sqlite3.connect(root / "state_5.sqlite")
    db.execute(
        """CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            updated_at_ms INTEGER,
            recency_at_ms INTEGER,
            title TEXT,
            rollout_path TEXT,
            archived INTEGER
        )"""
    )
    db.executemany("INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)", rows)
    db.commit()
    db.close()


class DiscoverTests(unittest.TestCase):
    def test_shared_database_rollout_path_is_quarantined_from_all_threads(self):
        first_id = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"
        second_id = "019f4aed-051d-71f3-900a-2495ad44f1b1"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sessions" / ("rollout-" + first_id + ".jsonl")
            write_rollout(path, first_id, {"type": "event"})
            write_threads_db(
                root,
                [
                    (first_id, NOW_MS - DAY_MS, 0, "First", str(path), 0),
                    (second_id, NOW_MS - 2 * DAY_MS, 0, "Second", str(path), 0),
                ],
            )

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual([item.session_id for item in found], [first_id, second_id])
            self.assertEqual(found[0].paths, [])
            self.assertEqual(found[1].paths, [])
            self.assertEqual(found[0].record_count, 0)
            self.assertEqual(found[1].size_bytes, 0)

    def test_database_paths_must_be_jsonl_under_session_directories(self):
        auth_id = "019f6511-86fc-7b60-9204-3e5f3ad94988"
        state_id = "019f209c-8aea-71a0-9342-9e9a92a03286"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            auth_path = root / "auth.jsonl"
            auth_path.write_text("not a rollout\n", encoding="utf-8")
            state_path = root / "state_5.sqlite"
            write_threads_db(root, [(auth_id, NOW_MS - DAY_MS, 0, "Auth", str(auth_path), 0), (state_id, NOW_MS, 0, "State", str(state_path), 0)])

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual([item.session_id for item in found], [state_id, auth_id])
            self.assertEqual(found[0].paths, [])
            self.assertEqual(found[1].paths, [])

    def test_rejects_database_paths_outside_root_including_symlink_escape(self):
        outside_id = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"
        symlink_id = "019f4aed-051d-71f3-900a-2495ad44f1b1"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "codex"
            root.mkdir()
            outside = base / "outside.jsonl"
            write_rollout(outside, outside_id)
            escape = root / "sessions" / "escape.jsonl"
            escape.parent.mkdir()
            escape.symlink_to(outside)
            write_threads_db(
                root,
                [
                    (outside_id, NOW_MS - DAY_MS, 0, "Outside", str(outside), 0),
                    (symlink_id, NOW_MS - 2 * DAY_MS, 0, "Escape", str(escape), 0),
                ],
            )

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual([item.session_id for item in found], [outside_id, symlink_id])
            self.assertEqual(found[0].paths, [])
            self.assertEqual(found[1].paths, [])
            self.assertEqual(found[0].record_count, 0)
            self.assertEqual(found[1].size_bytes, 0)

    def test_canonical_path_alias_is_counted_only_once(self):
        session_id = "019f6511-86fc-7b60-9204-3e5f3ad94988"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sessions" / ("rollout-" + session_id + ".jsonl")
            write_rollout(path, session_id, {"type": "event"})
            alias = path.parent / ".." / "sessions" / path.name
            write_threads_db(root, [(session_id, NOW_MS - DAY_MS, 0, "Alias", str(alias), 0)])

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual(found[0].paths, [path.resolve()])
            self.assertEqual(found[0].record_count, 2)
            self.assertEqual(found[0].size_bytes, path.stat().st_size)

    def test_database_id_overrides_conflicting_rollout_filename_id(self):
        database_id = "019f209c-8aea-71a0-9342-9e9a92a03286"
        filename_id = "019f209c-0f21-79f2-9fcb-a9d2d3877c81"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sessions" / ("rollout-" + filename_id + ".jsonl")
            write_rollout(path, filename_id, {"type": "event"})
            write_threads_db(root, [(database_id, NOW_MS - DAY_MS, 0, "DB identity", str(path), 0)])

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual([item.session_id for item in found], [database_id])
            self.assertEqual(found[0].paths, [path.resolve()])
            self.assertEqual(found[0].record_count, 2)
            self.assertEqual(found[0].size_bytes, path.stat().st_size)

    def test_includes_db_only_rows_and_uses_archived_metadata_source(self):
        missing_id = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_path = root / "archived_sessions" / "rollout-missing.jsonl"
            write_threads_db(root, [(missing_id, NOW_MS - DAY_MS, 0, "", str(missing_path), 1)])

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].session_id, missing_id)
            self.assertEqual(found[0].paths, [missing_path])
            self.assertEqual(found[0].record_count, 0)
            self.assertEqual(found[0].size_bytes, 0)
            self.assertEqual(found[0].source, "archived")
            self.assertEqual(found[0].title, "(untitled)")

    def test_database_id_associates_rollout_path_without_filename_or_metadata_uuid(self):
        session_id = "019f4aed-051d-71f3-900a-2495ad44f1b1"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sessions" / "rollout-without-id.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "From rollout"}})
                + "\n",
                encoding="utf-8",
            )
            write_threads_db(root, [(session_id, NOW_MS - DAY_MS, 0, "", str(path), 1)])

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].session_id, session_id)
            self.assertEqual(found[0].paths, [path])
            self.assertEqual(found[0].record_count, 1)
            self.assertEqual(found[0].source, "archived")
            self.assertEqual(found[0].title, "From rollout")

    def test_scalar_json_records_do_not_break_id_discovery(self):
        session_id = "019f6511-86fc-7b60-9204-3e5f3ad94988"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sessions" / "rollout-records.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(
                "[]\n" + json.dumps("scalar") + "\n" + json.dumps({"type": "session_meta", "payload": {"id": session_id}}) + "\n",
                encoding="utf-8",
            )

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual([item.session_id for item in found], [session_id])
            self.assertEqual(found[0].record_count, 3)

    def test_activity_exactly_at_cutoff_is_not_stale(self):
        session_id = "019f209c-8aea-71a0-9342-9e9a92a03286"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sessions" / ("rollout-" + session_id + ".jsonl")
            write_rollout(path, session_id)
            write_threads_db(root, [(session_id, NOW_MS - 30 * DAY_MS, 0, "Boundary", str(path), 0)])

            found = discover(root, NOW_MS, retention_days=30)

            self.assertFalse(found[0].stale)

    def test_merges_paths_and_uses_recent_database_update_even_for_old_filename(self):
        active_id = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"
        archive_id = "019f4aed-051d-71f3-900a-2495ad44f1b1"
        stale_id = "019f209c-8aea-71a0-9342-9e9a92a03286"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "sessions" / "2025" / "01" / ("rollout-2025-01-01T00-00-00-" + active_id + ".jsonl")
            archived = root / "archived_sessions" / ("rollout-2026-07-01T00-00-00-" + archive_id + ".jsonl")
            stale = root / "sessions" / "2024" / ("rollout-2024-01-01T00-00-00-" + stale_id + ".jsonl")
            write_rollout(active, active_id, {"type": "response_item"})
            write_rollout(archived, archive_id)
            write_rollout(stale, stale_id)
            old_seconds = (NOW_MS - 400 * DAY_MS) / 1000
            os.utime(active, (old_seconds, old_seconds))
            os.utime(stale, (old_seconds, old_seconds))
            write_threads_db(
                root,
                [
                    (active_id, NOW_MS - DAY_MS, 0, "Active title", str(active), 0),
                    (archive_id, 0, NOW_MS - 2 * DAY_MS, "Archived title", str(archived), 1),
                    (stale_id, NOW_MS - 400 * DAY_MS, 0, "Stale title", str(stale), 0),
                ],
            )

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual([item.session_id for item in found], [active_id, archive_id, stale_id])
            active_info = found[0]
            self.assertEqual(active_info.last_activity_ms, NOW_MS - DAY_MS)
            self.assertEqual(active_info.title, "Active title")
            self.assertEqual(active_info.record_count, 2)
            self.assertEqual(active_info.paths, [active])
            self.assertFalse(active_info.stale)
            self.assertEqual(found[1].source, "archived")
            self.assertTrue(found[2].stale)

    def test_deduplicates_session_meta_id_and_merges_file_statistics(self):
        session_id = "019f6511-86fc-7b60-9204-3e5f3ad94988"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "sessions" / "rollout-not-a-uuid.jsonl"
            second = root / "archived_sessions" / "copy.jsonl"
            write_rollout(first, session_id, {"type": "event"})
            write_rollout(second, session_id, {"type": "event"}, {"type": "event"})

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].session_id, str(UUID(session_id)))
            self.assertEqual(found[0].record_count, 5)
            self.assertEqual(found[0].paths, [first, second])
            self.assertEqual(found[0].size_bytes, first.stat().st_size + second.stat().st_size)

    def test_missing_database_uses_rollout_mtime_and_marks_stale(self):
        session_id = "019f209c-0f21-79f2-9fcb-a9d2d3877c81"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sessions" / ("rollout-2026-07-01T00-00-00-" + session_id + ".jsonl")
            write_rollout(path, session_id)
            old_seconds = (NOW_MS - 90 * DAY_MS) / 1000
            os.utime(path, (old_seconds, old_seconds))

            found = discover(root, NOW_MS, retention_days=30)

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].last_activity_ms, int(old_seconds * 1000))
            self.assertTrue(found[0].stale)


if __name__ == "__main__":
    unittest.main()
