import json
import tempfile
import unittest
from pathlib import Path

from scripts.retention.transaction import (
    CommitError,
    ensure_no_pending_journal,
    recover_transaction,
    commit_staged,
)
from scripts.retention.staging import stage_deletion

from tests.fixtures import snapshot_tree
from tests.test_staging import make_fixture


class TransactionTests(unittest.TestCase):
    def test_commit_replaces_staged_files_and_deletes_selected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, target_rollout, target_snapshot = make_fixture(root)
            before = snapshot_tree(root)
            transaction_dir = root.parent / f"retention-transaction-{root.name}"
            staged = stage_deletion(manifest, transaction_dir)

            report = commit_staged(staged)

            self.assertEqual(report.session_count, 1)
            self.assertFalse(target_rollout.exists())
            self.assertFalse(target_snapshot.exists())
            self.assertFalse(manifest.root.joinpath(".codex-session-retention.journal.json").exists())
            self.assertFalse(transaction_dir.exists())
            self.assertLess(len(snapshot_tree(root)), len(before))
            self.assertEqual(report.deleted_jsonl_rows, 3)
            self.assertGreater(report.freed_bytes, 0)
            ensure_no_pending_journal(root)

    def test_replacement_failure_restores_all_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _, _ = make_fixture(root)
            before = snapshot_tree(root)
            transaction_dir = root.parent / f"retention-transaction-{root.name}"
            staged = stage_deletion(manifest, transaction_dir)

            with self.assertRaises(CommitError):
                commit_staged(staged, fail_after=1)

            self.assertEqual(snapshot_tree(root), before)
            self.assertFalse(manifest.root.joinpath(".codex-session-retention.journal.json").exists())
            self.assertFalse(transaction_dir.exists())

    def test_pending_journal_blocks_and_recover_clears_empty_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / ".codex-session-retention.journal.json"
            journal.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "root": str(root),
                        "transaction_dir": str(root / "transaction"),
                        "entries": [],
                        "state": "pending",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(Exception):
                ensure_no_pending_journal(root)

            recover_transaction(journal)
            self.assertFalse(journal.exists())

    def test_global_file_change_after_staging_aborts_before_live_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _, _ = make_fixture(root)
            transaction_dir = root.parent / f"retention-transaction-{root.name}"
            staged = stage_deletion(manifest, transaction_dir)
            history = root / "history.jsonl"
            history.write_text(history.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
            changed = snapshot_tree(root)

            with self.assertRaises(CommitError):
                commit_staged(staged)

            self.assertEqual(snapshot_tree(root), changed)


if __name__ == "__main__":
    unittest.main()
