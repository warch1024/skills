import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.retention.cli import main, resolve_root

from tests.fixtures import DAY_MS, NOW_MS, snapshot_tree
from tests.test_staging import make_fixture


class CliTests(unittest.TestCase):
    def test_resolve_root_prefers_explicit_then_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            explicit = home / "explicit"
            explicit.mkdir()
            self.assertEqual(resolve_root(explicit, home / "ignored"), explicit.resolve())
            self.assertEqual(resolve_root(None, home / "codex"), (home / "codex").resolve())

    def test_list_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = snapshot_tree(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(
                    ["list", "--root", str(root), "--days", "7"],
                    clock_ms=lambda: NOW_MS,
                )

            self.assertEqual(result, 0)
            self.assertIn("最近 7 天", output.getvalue())
            self.assertEqual(snapshot_tree(root), before)

    def test_plan_writes_manifest_without_mutating_codex_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codex"
            root.mkdir()
            make_fixture(root)
            before = snapshot_tree(root)
            output_path = Path(tmp) / "planned.manifest"
            records_output = io.StringIO()
            with contextlib.redirect_stdout(records_output):
                result = main(
                    [
                        "plan",
                        "--root",
                        str(root),
                        "--days",
                        "7",
                        "--select",
                        "2",
                        "--output",
                        str(output_path),
                    ],
                    clock_ms=lambda: NOW_MS,
                )

            self.assertEqual(result, 0)
            self.assertTrue(output_path.exists())
            self.assertEqual(snapshot_tree(root), before)
            self.assertIn("manifest:", records_output.getvalue())

    def test_delete_requires_exact_confirmations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "fake.manifest"
            manifest_path.write_text("{}\n", encoding="utf-8")
            after_manifest = snapshot_tree(root)

            self.assertEqual(
                main(
                    [
                        "delete",
                        "--manifest",
                        str(manifest_path),
                        "--confirm",
                        "delete",
                        "--closed-confirmation",
                        "CLOSED",
                    ]
                ),
                2,
            )
            self.assertEqual(
                main(
                    [
                        "delete",
                        "--manifest",
                        str(manifest_path),
                        "--confirm",
                        "DELETE",
                        "--closed-confirmation",
                        "closed",
                    ]
                ),
                2,
            )
            self.assertEqual(snapshot_tree(root), after_manifest)

    def test_delete_executes_complete_transaction_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, target_rollout, target_snapshot = make_fixture(root)
            records_output = io.StringIO()
            manifest_path = Path(tmp) / "planned.manifest"
            with contextlib.redirect_stdout(records_output):
                plan_result = main(
                    [
                        "plan",
                        "--root",
                        str(root),
                        "--days",
                        "7",
                        "--select",
                        "2",
                        "--output",
                        str(manifest_path),
                    ],
                    clock_ms=lambda: NOW_MS,
                )
            self.assertEqual(plan_result, 0)

            with contextlib.redirect_stdout(io.StringIO()):
                delete_result = main(
                    [
                        "delete",
                        "--manifest",
                        str(manifest_path),
                        "--confirm",
                        "DELETE",
                        "--closed-confirmation",
                        "CLOSED",
                    ]
                )

            self.assertEqual(delete_result, 0)
            self.assertFalse(target_rollout.exists())
            self.assertFalse(target_snapshot.exists())
            self.assertFalse(manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
