#!/usr/bin/env python3
"""Unit tests for resume-from-agent extract-session.py (temp fixtures only)."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "resume-from-agent" / "scripts" / "extract-session.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("extract_session", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_session"] = mod
    spec.loader.exec_module(mod)
    return mod


class ExtractSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_clean_skill_injections_strips_and_labels(self):
        text, skills = self.mod.clean_skill_injections(
            '<skill name="tdd">body</skill>\nplease continue'
        )
        self.assertIn("tdd", skills)
        self.assertIn("[skill]", text)
        self.assertIn("please continue", text)

    def test_strip_session_context(self):
        raw = "<session_context>huge</session_context>\nreal goal"
        self.assertEqual(self.mod.strip_session_context(raw), "real goal")

    def test_path_from_mapping_skips_shellish(self):
        self.assertIsNone(
            self.mod.path_from_mapping("bash", {"command": "ls -la"})
        )
        self.assertEqual(
            self.mod.path_from_mapping(
                "read_file", {"file_path": "src/main.ts"}
            ),
            "src/main.ts",
        )

    def test_same_cwd_resolves(self):
        home = str(Path.home())
        self.assertTrue(self.mod.same_cwd(home, str(Path.home().resolve())))

    def test_discover_and_extract_goose_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sessions = tmp_path / "sessions"
            sessions.mkdir()
            cwd = str(tmp_path / "project")
            Path(cwd).mkdir()
            session_path = sessions / "20250101_120000.jsonl"
            meta = {
                "working_dir": cwd,
                "description": "fix the flaky test",
                "message_count": 2,
            }
            lines = [
                json.dumps(meta),
                json.dumps(
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "fix the flaky test"}],
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Looking at the test file.",
                            },
                            {
                                "type": "toolRequest",
                                "toolCall": {
                                    "value": {
                                        "name": "developer__text_editor",
                                        "arguments": {
                                            "path": "tests/test_flaky.py"
                                        },
                                    }
                                },
                            },
                        ],
                    }
                ),
            ]
            session_path.write_text("\n".join(lines) + "\n")

            original = self.mod.goose_sessions_dir
            self.mod.goose_sessions_dir = lambda: sessions  # type: ignore
            try:
                cands = self.mod.discover_goose(cwd, None)
                self.assertEqual(len(cands), 1)
                self.assertEqual(cands[0].agent, "goose")
                brief = self.mod.extract_goose(cands[0])
                rendered = self.mod.render_brief(brief)
            finally:
                self.mod.goose_sessions_dir = original  # type: ignore

            self.assertIn("agent: goose", rendered)
            self.assertIn("fix the flaky test", rendered)
            self.assertIn("tests/test_flaky.py", rendered)
            self.assertIn("developer__text_editor", rendered)

    def test_discover_hermes_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "state.db"
            cwd = str(tmp_path / "ws")
            Path(cwd).mkdir()
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE sessions (
                  id TEXT PRIMARY KEY,
                  title TEXT,
                  cwd TEXT,
                  model TEXT,
                  started_at REAL,
                  ended_at REAL,
                  message_count INTEGER,
                  git_branch TEXT,
                  end_reason TEXT,
                  source TEXT,
                  active INTEGER DEFAULT 1
                );
                CREATE TABLE messages (
                  id INTEGER PRIMARY KEY,
                  session_id TEXT,
                  role TEXT,
                  content TEXT,
                  tool_calls TEXT,
                  tool_name TEXT,
                  timestamp REAL,
                  finish_reason TEXT,
                  active INTEGER DEFAULT 1
                );
                """
            )
            conn.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "sess_abc",
                    "Ship resume skill",
                    cwd,
                    "test-model",
                    1_700_000_000,
                    1_700_000_100,
                    2,
                    "main",
                    None,
                    "cli",
                    1,
                ),
            )
            conn.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    1,
                    "sess_abc",
                    "user",
                    "Implement resume-from-agent",
                    None,
                    None,
                    1_700_000_000,
                    None,
                    1,
                ),
            )
            tool_calls = json.dumps(
                [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps(
                                {"path": "skills/resume-from-agent/SKILL.md"}
                            ),
                        }
                    }
                ]
            )
            conn.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    2,
                    "sess_abc",
                    "assistant",
                    "Reading the skill file.",
                    tool_calls,
                    None,
                    1_700_000_050,
                    "tool_calls",
                    1,
                ),
            )
            conn.commit()
            conn.close()

            original = self.mod.hermes_db
            self.mod.hermes_db = lambda: db_path  # type: ignore
            try:
                cands = self.mod.discover_hermes(cwd, None)
                self.assertEqual(len(cands), 1)
                brief = self.mod.extract_hermes(cands[0])
                text = self.mod.render_brief(brief)
            finally:
                self.mod.hermes_db = original  # type: ignore

            self.assertIn("agent: hermes", text)
            self.assertIn("sess_abc", text)
            self.assertIn("Implement resume-from-agent", text)
            self.assertIn("skills/resume-from-agent/SKILL.md", text)
            self.assertIn("read_file", text)

    def test_discover_gemini_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project = tmp_path / "proj"
            project.mkdir()
            gem_tmp = tmp_path / "gemini-tmp" / "hash1"
            chats = gem_tmp / "chats"
            chats.mkdir(parents=True)
            (gem_tmp / ".project_root").write_text(str(project))
            session = chats / "session-2026-01-01T00-00-deadbeef.jsonl"
            header = {
                "sessionId": "deadbeef-0001",
                "projectHash": "hash1",
                "startTime": "2026-01-01T00:00:00Z",
            }
            user = {
                "type": "user",
                "content": (
                    "<session_context>noise</session_context>\n"
                    "Please ship the skill"
                ),
            }
            model = {
                "type": "gemini",
                "model": "gemini-test",
                "content": "On it.",
                "toolCalls": [
                    {
                        "name": "read_file",
                        "args": {"file_path": "README.md"},
                    }
                ],
            }
            session.write_text(
                "\n".join(json.dumps(x) for x in (header, user, model)) + "\n"
            )

            original = self.mod.gemini_tmp_root
            self.mod.gemini_tmp_root = lambda: gem_tmp.parent  # type: ignore
            try:
                cands = self.mod.discover_gemini(str(project), None)
                self.assertEqual(len(cands), 1)
                brief = self.mod.extract_gemini(cands[0])
                text = self.mod.render_brief(brief)
            finally:
                self.mod.gemini_tmp_root = original  # type: ignore

            self.assertIn("agent: gemini", text)
            self.assertIn("Please ship the skill", text)
            self.assertNotIn("<session_context>", text)
            self.assertIn("README.md", text)

    def test_pick_candidate_notes_close_runner_up(self):
        a = self.mod.Candidate(
            agent="hermes", session_id="1", cwd="/x", mtime=1000.0
        )
        b = self.mod.Candidate(
            agent="goose", session_id="2", cwd="/x", mtime=980.0
        )
        winner, notes = self.mod.pick_candidate([a, b])
        self.assertEqual(winner.agent, "hermes")
        self.assertTrue(any("runner-up" in n for n in notes))

    def test_main_list_empty_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            from contextlib import redirect_stdout
            import io

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = self.mod.main(
                    ["--cwd", tmp, "--agent", "auggie", "--list"]
                )
            self.assertEqual(code, 1)
            self.assertIn("No matching sessions", buf.getvalue())

    def test_main_unknown_agent(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.main(["--cwd", "/tmp", "--agent", "not-a-real-agent"])
        self.assertIn("Unknown agent", str(ctx.exception))

    def test_stamp_harness_renames_foreign_agent_field(self):
        raw = "# OpenCode session brief\nagent: build\nsession_id: ses_1\n"
        stamped = self.mod.stamp_harness(raw, "opencode")
        self.assertIn("agent: opencode", stamped)
        self.assertIn("session_agent: build", stamped)
        self.assertNotIn("\nagent: build\n", "\n" + stamped)

    def test_render_brief_has_resume_instruction(self):
        brief = self.mod.Brief(
            agent="test",
            session_id="s1",
            opening_users=["do the thing"],
            recent_turns=[{"role": "user", "text": "do the thing"}],
            ending="stopped mid way",
        )
        text = self.mod.render_brief(brief)
        self.assertIn("## Resume instruction", text)
        self.assertIn("Do not summarise and wait", text)

    def test_cross_agent_ranking(self):
        """discover_all ranks by mtime across adapters (goose fixture only)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sessions = tmp_path / "sessions"
            sessions.mkdir()
            cwd = str(tmp_path / "project")
            Path(cwd).mkdir()
            older = sessions / "old.jsonl"
            newer = sessions / "new.jsonl"
            for path, desc, mtime in (
                (older, "older work", 1_000),
                (newer, "newer work", 2_000),
            ):
                path.write_text(
                    json.dumps(
                        {
                            "working_dir": cwd,
                            "description": desc,
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": desc}],
                        }
                    )
                    + "\n"
                )
                os.utime(path, (mtime, mtime))

            original = self.mod.goose_sessions_dir
            self.mod.goose_sessions_dir = lambda: sessions  # type: ignore
            try:
                # Force goose only so other live home stores don't win.
                ranked = self.mod.discover_all(cwd, None, "goose")
            finally:
                self.mod.goose_sessions_dir = original  # type: ignore

            self.assertGreaterEqual(len(ranked), 2)
            self.assertEqual(ranked[0].session_id, "new")
            self.assertEqual(ranked[1].session_id, "old")


if __name__ == "__main__":
    unittest.main()
