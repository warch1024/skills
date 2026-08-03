import unittest
from pathlib import Path

from scripts.retention.display import SelectionError, format_session_table, parse_selection
from scripts.retention.model import SessionRecord


RECENT_ID = "019f687c-0f21-79f2-9fcb-a9d2d3877c81"
STALE_ID = "019f209c-8aea-71a0-9342-9e9a92a03286"
CUTOFF_MS = 2_000_000_000_000


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            SessionRecord(
                session_id=RECENT_ID,
                last_activity_ms=CUTOFF_MS + 1,
                activity_source="updated_at_ms",
                title="Recent",
                paths=(Path("/tmp/codex/sessions/recent.jsonl"),),
                snapshot_paths=(),
                file_count=1,
                record_count=2,
                size_bytes=1024,
                archived=False,
                ambiguous=(),
            ),
            SessionRecord(
                session_id=STALE_ID,
                last_activity_ms=CUTOFF_MS - 1,
                activity_source="mtime",
                title="Stale",
                paths=(),
                snapshot_paths=(),
                file_count=0,
                record_count=0,
                size_bytes=0,
                archived=True,
                ambiguous=("missing rollout",),
            ),
        ]

    def test_listing_has_recent_and_stale_sections_and_required_columns(self):
        text = format_session_table(self.records, cutoff_ms=CUTOFF_MS, days=7)

        self.assertIn("最近 7 天，共 1 个", text)
        self.assertIn("大于 7 天，共 1 个", text)
        self.assertIn(RECENT_ID, text)
        self.assertIn(STALE_ID, text)
        self.assertIn("文件数", text)
        self.assertIn("记录数", text)
        self.assertIn("空间", text)
        self.assertLess(text.index(RECENT_ID), text.index("大于 7 天"))
        self.assertLess(text.index("大于 7 天"), text.index(STALE_ID))

    def test_selection_parser_accepts_ranges_and_rejects_duplicates(self):
        self.assertEqual(parse_selection("8,9-11", 12), (8, 9, 10, 11))
        self.assertEqual(parse_selection(" 1 ", 2), (1,))
        for value in ("", "0", "13", "9-8", "8,8", "a"):
            with self.subTest(value=value), self.assertRaises(SelectionError):
                parse_selection(value, 12)


if __name__ == "__main__":
    unittest.main()
