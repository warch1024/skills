import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.retention.discovery import discover_sessions
from scripts.retention.manifest import build_manifest
from scripts.retention.staging import stage_deletion

from tests.fixtures import (
    DAY_MS,
    NOW_MS,
    create_goals_db,
    create_logs_db,
    create_memories_db,
    create_state_db,
    snapshot_tree,
    write_jsonl,
    write_rollout,
    write_shell_snapshot,
)


TARGET_ID = "019f209c-8aea-71a0-9342-9e9a92a03286"
OTHER_ID = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"


def make_fixture(root: Path):
    target_rollout = write_rollout(root, TARGET_ID, title="Target")
    other_rollout = write_rollout(root, OTHER_ID, title="Other")
    target_snapshot = write_shell_snapshot(root, TARGET_ID, TARGET_ID)
    write_shell_snapshot(root, OTHER_ID, OTHER_ID)
    write_jsonl(
        root / "session_index.jsonl",
        [{"id": TARGET_ID, "thread_name": "Target"}, {"id": OTHER_ID, "thread_name": "Other"}],
    )
    write_jsonl(
        root / "history.jsonl",
        [
            {"session_id": TARGET_ID, "ts": 1, "text": "target command"},
            {"session_id": OTHER_ID, "ts": 2, "text": f"mentions {TARGET_ID} as text"},
            {"session_id": TARGET_ID, "ts": 3, "text": "second target command"},
        ],
    )
    create_state_db(
        root,
        [
            (TARGET_ID, NOW_MS - 10 * DAY_MS, 0, "Target", str(target_rollout), 0),
            (OTHER_ID, NOW_MS - DAY_MS, 0, "Other", str(other_rollout), 0),
        ],
        dynamic_tools=[(TARGET_ID, 0, "target"), (OTHER_ID, 0, "other")],
        spawn_edges=[
            (TARGET_ID, OTHER_ID, "target-parent"),
            (OTHER_ID, TARGET_ID, "target-child"),
        ],
    )
    create_goals_db(root, [(TARGET_ID, "goal-target", "complete"), (OTHER_ID, "goal-other", "active")])
    create_memories_db(root, [(TARGET_ID, "memory-target"), (OTHER_ID, "memory-other")])
    create_logs_db(root, [(1, TARGET_ID, "target log"), (2, OTHER_ID, f"mentions {TARGET_ID}")])
    records = discover_sessions(root, NOW_MS, retention_days=7)
    target_number = next(index for index, record in enumerate(records, 1) if record.session_id == TARGET_ID)
    manifest = build_manifest(root, records, (target_number,), NOW_MS - 7 * DAY_MS, allow_fresh=False)
    return manifest, target_rollout, target_snapshot


class StagingTests(unittest.TestCase):
    def test_stage_removes_only_structured_session_references_and_preserves_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, target_rollout, target_snapshot = make_fixture(root)
            before = snapshot_tree(root)
            transaction_dir = root.parent / f"retention-transaction-{root.name}"

            staged = stage_deletion(manifest, transaction_dir)

            try:
                self.assertEqual(snapshot_tree(root), before)
                self.assertIn(target_rollout.resolve(), staged.deletion_paths)
                self.assertIn(target_snapshot.resolve(), staged.deletion_paths)
                self.assertEqual(dict(staged.jsonl_rows)["history.jsonl"], 2)
                self.assertEqual(dict(staged.sqlite_rows)["state_5.sqlite.threads"], 1)
                self.assertEqual(dict(staged.sqlite_rows)["state_5.sqlite.thread_dynamic_tools"], 1)
                self.assertEqual(dict(staged.sqlite_rows)["state_5.sqlite.thread_spawn_edges"], 2)
                self.assertEqual(dict(staged.sqlite_rows)["goals_1.sqlite.thread_goals"], 1)
                self.assertEqual(dict(staged.sqlite_rows)["memories_1.sqlite.stage1_outputs"], 1)
                self.assertEqual(dict(staged.sqlite_rows)["logs_2.sqlite.logs"], 1)

                replacements = dict(staged.replacements)
                staged_history = replacements[(root / "history.jsonl").resolve()]
                history = [json.loads(line) for line in staged_history.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["session_id"], OTHER_ID)
                self.assertIn(TARGET_ID, history[0]["text"])

                staged_state = replacements[(root / "state_5.sqlite").resolve()]
                connection = sqlite3.connect(staged_state)
                self.assertEqual(connection.execute("SELECT count(*) FROM threads WHERE id = ?", (TARGET_ID,)).fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT count(*) FROM threads").fetchone()[0], 1)
                connection.close()
            finally:
                shutil.rmtree(transaction_dir, ignore_errors=True)

    def test_stage_refuses_incompatible_existing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _, _ = make_fixture(root)
            (root / "goals_1.sqlite").unlink()
            (root / "goals_1.sqlite").write_bytes(b"not sqlite")

            with self.assertRaises(Exception):
                stage_deletion(manifest, root.parent / f"retention-transaction-{root.name}")


if __name__ == "__main__":
    unittest.main()
