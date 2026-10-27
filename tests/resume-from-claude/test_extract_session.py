#!/usr/bin/env python3
"""Unit tests for resume-from-claude extract-session.py."""

from __future__ import annotations

from functools import partial
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import isolated_env, load_skill_script, make_workspace_symlink_pair, run_cli

load_mod = partial(load_skill_script, "resume-from-claude", "extract-session.py")


class EncodeCwdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_plain_path(self):
        self.assertEqual(
            self.mod.encode_cwd("/Users/foo/bar"), "-Users-foo-bar"
        )

    def test_dotted_path_components_are_sanitized(self):
        # Claude Code sanitizes [^A-Za-z0-9_-] to "-", including dots, and
        # preserves repeated hyphens (e.g. ".fleet" -> "-fleet").
        self.assertEqual(
            self.mod.encode_cwd(
                "/Users/jonathanbaldie/Code-2/github.com/jonbaldie/skills"
            ),
            "-Users-jonathanbaldie-Code-2-github-com-jonbaldie-skills",
        )
        self.assertEqual(
            self.mod.encode_cwd("/Users/jonathanbaldie/.fleet/worktrees/x"),
            "-Users-jonathanbaldie--fleet-worktrees-x",
        )

    def test_other_special_characters_are_sanitized(self):
        self.assertEqual(
            self.mod.encode_cwd("/Users/foo/my project (v2)"),
            "-Users-foo-my-project--v2-",
        )


class ResolveSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def _home(self, tmp: str) -> Path:
        home = Path(tmp)
        self.enterContext(isolated_env(HOME=str(home)))
        return home

    _cwd_pair = staticmethod(make_workspace_symlink_pair)

    def _project(self, home: Path, cwd: Path) -> Path:
        return home / ".claude" / "projects" / self.mod.encode_cwd(str(cwd))

    def _write_session(
        self, project: Path, session_id: str, prompt: str, cwd: Path
    ) -> Path:
        project.mkdir(parents=True, exist_ok=True)
        session = project / f"{session_id}.jsonl"
        session.write_text(
            json.dumps(
                {
                    "type": "user",
                    "cwd": str(cwd),
                    "sessionId": session_id,
                    "message": {"content": [{"type": "text", "text": prompt}]},
                }
            )
            + "\n"
        )
        return session

    def _render(self, args: list[str]) -> str:
        return run_cli(self.mod.main, args)

    def test_symlinked_cwd_finds_session_under_physical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, symlink_cwd = self._cwd_pair(home)
            self._write_session(
                self._project(home, physical_cwd.resolve()),
                "claude-physical-session",
                "claude physical prompt",
                physical_cwd.resolve(),
            )

            output = self._render(["--cwd", str(symlink_cwd)])

            self.assertIn("session_id: claude-physical-session", output)
            self.assertIn("claude physical prompt", output)

    def test_physical_cwd_still_finds_its_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, _ = self._cwd_pair(home)
            self._write_session(
                self._project(home, physical_cwd),
                "claude-direct-session",
                "claude direct prompt",
                physical_cwd,
            )

            output = self._render(["--cwd", str(physical_cwd)])

            self.assertIn("session_id: claude-direct-session", output)
            self.assertIn("claude direct prompt", output)

    def test_both_cwd_keys_choose_the_newest_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, symlink_cwd = self._cwd_pair(home)
            logical_session = self._write_session(
                self._project(home, symlink_cwd),
                "claude-logical-session",
                "older logical prompt",
                symlink_cwd,
            )
            physical_session = self._write_session(
                self._project(home, physical_cwd.resolve()),
                "claude-physical-session",
                "newer physical prompt",
                physical_cwd.resolve(),
            )
            os.utime(logical_session, (1_700_000_000, 1_700_000_000))
            os.utime(physical_session, (1_700_003_600, 1_700_003_600))

            output = self._render(["--cwd", str(symlink_cwd)])

            self.assertIn("session_id: claude-physical-session", output)
            self.assertIn("newer physical prompt", output)
            self.assertNotIn("claude-logical-session", output)

    def test_session_id_and_jsonl_lookups_remain_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, symlink_cwd = self._cwd_pair(home)
            by_id = self._write_session(
                self._project(home, physical_cwd),
                "claude-explicit-session",
                "explicit id prompt",
                physical_cwd,
            )
            by_jsonl = self._write_session(
                home,
                "claude-jsonl-session",
                "explicit jsonl prompt",
                physical_cwd,
            )

            id_output = self._render(
                ["--cwd", str(symlink_cwd), "claude-explicit-session"]
            )
            jsonl_output = self._render(
                ["--cwd", str(symlink_cwd), "--jsonl", str(by_jsonl)]
            )

            self.assertIn("explicit id prompt", id_output)
            self.assertIn(str(by_id), id_output)
            self.assertIn("explicit jsonl prompt", jsonl_output)
            self.assertIn(str(by_jsonl), jsonl_output)

    def test_resolve_session_honors_claude_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, _ = self._cwd_pair(home)
            custom_claude = Path(tmp) / "custom_claude"
            custom_project = (
                custom_claude
                / "projects"
                / self.mod.encode_cwd(str(physical_cwd))
            )
            custom_session = self._write_session(
                custom_project,
                "custom-claude-session",
                "custom config dir prompt",
                physical_cwd,
            )

            # Stale session in default ~/.claude with newer mtime
            stale_project = self._project(home, physical_cwd)
            stale_session = self._write_session(
                stale_project,
                "stale-claude-session",
                "stale default prompt",
                physical_cwd,
            )
            os.utime(stale_session, (1_800_000_000, 1_800_000_000))

            old_config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
            try:
                os.environ["CLAUDE_CONFIG_DIR"] = str(custom_claude)
                output = self._render(["--cwd", str(physical_cwd)])
                self.assertIn("session_id: custom-claude-session", output)
                self.assertIn("custom config dir prompt", output)
                self.assertNotIn("stale default prompt", output)
            finally:
                if old_config_dir is None:
                    os.environ.pop("CLAUDE_CONFIG_DIR", None)
                else:
                    os.environ["CLAUDE_CONFIG_DIR"] = old_config_dir

    def test_claude_config_dir_empty_or_unset_falls_back_to_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, _ = self._cwd_pair(home)
            self._write_session(
                self._project(home, physical_cwd),
                "default-claude-session",
                "default prompt",
                physical_cwd,
            )

            old_config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
            try:
                os.environ.pop("CLAUDE_CONFIG_DIR", None)
                output = self._render(["--cwd", str(physical_cwd)])
                self.assertIn("default-claude-session", output)

                os.environ["CLAUDE_CONFIG_DIR"] = ""
                output2 = self._render(["--cwd", str(physical_cwd)])
                self.assertIn("default-claude-session", output2)
            finally:
                if old_config_dir is None:
                    os.environ.pop("CLAUDE_CONFIG_DIR", None)
                else:
                    os.environ["CLAUDE_CONFIG_DIR"] = old_config_dir



if __name__ == "__main__":
    unittest.main()
