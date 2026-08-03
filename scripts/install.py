#!/usr/bin/env python3
"""Install the Skill payload and independent terminal wrapper atomically."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import uuid
from pathlib import Path


class InstallError(RuntimeError):
    pass


def _copy_payload(repo_root: Path, destination: Path) -> None:
    required = (
        repo_root / "SKILL.md",
        repo_root / "agents/openai.yaml",
        repo_root / "scripts/codex_session_retention.py",
        repo_root / "scripts/retention",
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        raise InstallError(f"missing install payload: {missing[0]}")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copy2(repo_root / "SKILL.md", destination / "SKILL.md")
    shutil.copytree(repo_root / "agents", destination / "agents")
    scripts = destination / "scripts"
    scripts.mkdir(mode=0o700)
    shutil.copy2(repo_root / "scripts/codex_session_retention.py", scripts / "codex_session_retention.py")
    shutil.copytree(
        repo_root / "scripts/retention",
        scripts / "retention",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    os.chmod(scripts / "codex_session_retention.py", 0o755)


def _wrapper_text() -> str:
    return """#!/bin/sh
set -eu
CODEX_HOME=\"${CODEX_HOME:-$HOME/.codex}\"
PYTHONDONTWRITEBYTECODE=1 exec python3 \"$CODEX_HOME/skills/codex-session-retention/scripts/codex_session_retention.py\" \"$@\"
"""


def _replace_directory(source: Path, target: Path) -> Path | None:
    backup = None
    if target.exists():
        backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
        os.replace(target, backup)
    os.replace(source, target)
    return backup


def install(
    *,
    repo_root: Path | None = None,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> None:
    repo_root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    home = Path(home or Path.home()).expanduser().resolve()
    codex_home = Path(codex_home or os.environ.get("CODEX_HOME", home / ".codex")).expanduser().resolve()
    skill_target = codex_home / "skills/codex-session-retention"
    wrapper_target = home / ".local/bin/codex-session-retention"
    skill_target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    wrapper_target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    temporary_parent = Path(tempfile.mkdtemp(prefix="codex-session-retention-install-", dir=str(skill_target.parent)))
    staged_skill = temporary_parent / "codex-session-retention"
    old_skill = None
    old_wrapper = None
    wrapper_stage = temporary_parent / "codex-session-retention.wrapper"
    try:
        _copy_payload(repo_root, staged_skill)
        wrapper_stage.write_text(_wrapper_text(), encoding="utf-8")
        os.chmod(wrapper_stage, 0o755)
        old_skill = _replace_directory(staged_skill, skill_target)
        if wrapper_target.exists():
            old_wrapper = wrapper_target.parent / f".{wrapper_target.name}.backup-{uuid.uuid4().hex}"
            os.replace(wrapper_target, old_wrapper)
        os.replace(wrapper_stage, wrapper_target)
    except Exception as exc:
        if skill_target.exists() and old_skill is not None:
            shutil.rmtree(skill_target, ignore_errors=True)
            os.replace(old_skill, skill_target)
        if wrapper_target.exists() and old_wrapper is not None:
            wrapper_target.unlink()
            os.replace(old_wrapper, wrapper_target)
        raise InstallError(str(exc)) from exc
    else:
        if old_skill is not None:
            shutil.rmtree(old_skill, ignore_errors=True)
        if old_wrapper is not None:
            old_wrapper.unlink(missing_ok=True)
    finally:
        shutil.rmtree(temporary_parent, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Codex Session Retention")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--codex-home", type=Path)
    args = parser.parse_args(argv)
    try:
        install(repo_root=args.repo_root, home=args.home, codex_home=args.codex_home)
    except InstallError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
