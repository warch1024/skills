import os
import tempfile
import unittest
from pathlib import Path

from scripts.install import install


class InstallTests(unittest.TestCase):
    def test_installer_creates_skill_and_external_wrapper_without_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "SKILL.md").write_text("skill\n", encoding="utf-8")
            (root / "agents").mkdir()
            (root / "agents/openai.yaml").write_text("interface: {}\n", encoding="utf-8")
            (root / "scripts/retention").mkdir(parents=True)
            (root / "scripts/codex_session_retention.py").write_text("entry\n", encoding="utf-8")
            (root / "scripts/retention/core.py").write_text("core\n", encoding="utf-8")
            (root / "scripts/retention/__pycache__").mkdir()
            (root / "scripts/retention/__pycache__/core.pyc").write_bytes(b"cache")
            (root / "tests").mkdir()
            (root / "tests/test_only.py").write_text("test\n", encoding="utf-8")
            home = Path(tmp) / "home"
            codex_home = home / ".codex"

            install(repo_root=root, home=home, codex_home=codex_home)

            skill = codex_home / "skills/codex-session-retention"
            wrapper = home / ".local/bin/codex-session-retention"
            self.assertTrue((skill / "SKILL.md").is_file())
            self.assertTrue((skill / "scripts/retention/core.py").is_file())
            self.assertFalse((skill / "scripts/retention/__pycache__").exists())
            self.assertFalse((skill / "tests").exists())
            self.assertTrue(wrapper.stat().st_mode & 0o111)
            self.assertIn('${CODEX_HOME:-$HOME/.codex}', wrapper.read_text(encoding="utf-8"))
            self.assertIn("PYTHONDONTWRITEBYTECODE=1", wrapper.read_text(encoding="utf-8"))

    def test_installer_replaces_existing_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            (root / "agents").mkdir(parents=True)
            (root / "scripts/retention").mkdir(parents=True)
            (root / "SKILL.md").write_text("new\n", encoding="utf-8")
            (root / "agents/openai.yaml").write_text("new\n", encoding="utf-8")
            (root / "scripts/codex_session_retention.py").write_text("entry\n", encoding="utf-8")
            (root / "scripts/retention/core.py").write_text("core\n", encoding="utf-8")
            home = Path(tmp) / "home"
            codex_home = home / ".codex"
            target = codex_home / "skills/codex-session-retention"
            target.mkdir(parents=True)
            (target / "old.txt").write_text("old\n", encoding="utf-8")

            install(repo_root=root, home=home, codex_home=codex_home)

            self.assertFalse((target / "old.txt").exists())
            self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "new\n")


if __name__ == "__main__":
    unittest.main()
