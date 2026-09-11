#!/usr/bin/env python3
"""Unit tests for resume-from-claude extract-session.py (encoder only)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "resume-from-claude" / "scripts" / "extract-session.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("extract_session_rfc", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_session_rfc"] = mod
    spec.loader.exec_module(mod)
    return mod


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


if __name__ == "__main__":
    unittest.main()
