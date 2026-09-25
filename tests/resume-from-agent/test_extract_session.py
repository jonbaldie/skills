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

    def _write_hermes_db(self, db_path: Path, cwd: str = "/ws"):
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
        conn.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)",
            (
                2,
                "sess_abc",
                "assistant",
                "Done reading.",
                None,
                None,
                1_700_000_050,
                "stop",
                1,
            ),
        )
        conn.commit()
        conn.close()

    def _write_codex_rollout(self, path: Path):
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "rollout-xyz",
                        "cwd": "/ws",
                        "git": {"branch": "main"},
                    },
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:01Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Ship the PR"}
                        ],
                    },
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:02Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "All shipped."}
                        ],
                    },
                }
            ),
        ]
        path.write_text("\n".join(lines) + "\n")

    def test_discover_codex_by_thread_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sessions_dir = (
                tmp_path / ".codex" / "sessions" / "2026" / "01" / "01"
            )
            sessions_dir.mkdir(parents=True)
            rollout = sessions_dir / (
                "rollout-2026-01-01T00-00-00-rollout-xyz.jsonl"
            )
            self._write_codex_rollout(rollout)
            index_file = tmp_path / ".codex" / "session_index.jsonl"
            index_file.write_text(
                json.dumps(
                    {"id": "rollout-xyz", "thread_name": "Ship the PR"}
                )
                + "\n"
            )

            original_home = self.mod.home
            self.mod.home = lambda: tmp_path  # type: ignore
            try:
                candidates = self.mod.discover_codex("/ws", "Ship the PR")
            finally:
                self.mod.home = original_home  # type: ignore

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].agent, "codex")
            self.assertEqual(candidates[0].path, str(rollout))

    def _main_output(self, argv):
        from contextlib import redirect_stdout
        import io

        buf = io.StringIO()
        code = None
        try:
            with redirect_stdout(buf):
                code = self.mod.main(argv)
        except SystemExit as exc:
            code = exc
        return code, buf.getvalue()

    def test_path_agent_hermes_uses_hermes_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            self._write_hermes_db(db_path)
            code, out = self._main_output(
                ["--agent", "hermes", "--path", str(db_path)]
            )
            self.assertEqual(code, 0)
            self.assertIn("agent: hermes", out)
            self.assertIn("session_id: sess_abc", out)
            self.assertIn("Implement resume-from-agent", out)
            self.assertIn("Done reading.", out)

    def test_path_agent_codex_parses_rollout(self):
        with tempfile.TemporaryDirectory() as tmp:
            rollout = Path(tmp) / "rollout-xyz.jsonl"
            self._write_codex_rollout(rollout)
            code, out = self._main_output(
                ["--agent", "codex", "--path", str(rollout)]
            )
            self.assertEqual(code, 0)
            self.assertIn("agent: codex", out)
            self.assertIn("Ship the PR", out)
            self.assertIn("All shipped.", out)

    def test_path_agent_mismatch_fails_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            self._write_hermes_db(db_path)
            with self.assertRaises(SystemExit) as ctx:
                self.mod.main(
                    ["--agent", "codex", "--path", str(db_path)]
                )
            message = str(ctx.exception)
            self.assertIn("codex", message)
            self.assertIn(str(db_path), message)

    def test_path_no_agent_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            self._write_hermes_db(db_path)
            code, out = self._main_output(["--path", str(db_path)])
            self.assertEqual(code, 0)
            self.assertIn("agent: agy", out)
            self.assertIn("session_id: state", out)

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

    def test_encode_claude_cwd_sanitizes_dots(self):
        # Claude Code sanitizes [^A-Za-z0-9_-] to "-", including dots, and
        # preserves repeated hyphens (e.g. ".fleet" -> "-fleet").
        self.assertEqual(
            self.mod.encode_claude_cwd(
                "/Users/jonathanbaldie/Code-2/github.com/jonbaldie/skills"
            ),
            "-Users-jonathanbaldie-Code-2-github-com-jonbaldie-skills",
        )
        self.assertEqual(
            self.mod.encode_claude_cwd("/Users/jonathanbaldie/.fleet/worktrees/x"),
            "-Users-jonathanbaldie--fleet-worktrees-x",
        )
        self.assertEqual(
            self.mod.encode_claude_cwd("/Users/foo/bar"), "-Users-foo-bar"
        )

    def test_encode_cursor_cwd_sanitizes_dots(self):
        # Cursor strips the leading "/" then sanitizes [^A-Za-z0-9_-] to "-".
        self.assertEqual(
            self.mod.encode_cursor_cwd(
                "/Users/jonathanbaldie/go/src/github.com/jonbaldie/gastown"
            ),
            "Users-jonathanbaldie-go-src-github-com-jonbaldie-gastown",
        )
        self.assertEqual(
            self.mod.encode_cursor_cwd("/Users/jonathanbaldie/.fleet/x"),
            "Users-jonathanbaldie--fleet-x",
        )
        self.assertEqual(
            self.mod.encode_cursor_cwd("/Users/foo/bar"), "Users-foo-bar"
        )

    def test_discover_claude_dotted_cwd_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / ".claude" / "projects"
            project = root / self.mod.encode_claude_cwd(
                str(tmp_path / "github.com/x/y")
            )
            project.mkdir(parents=True)
            session = project / "abc.jsonl"
            session.write_text(
                json.dumps({"cwd": str(tmp_path / "github.com/x/y")}) + "\n"
            )
            original = self.mod.home
            self.mod.home = lambda: tmp_path  # type: ignore
            try:
                cands = self.mod.discover_claude(
                    str(tmp_path / "github.com/x/y"), None
                )
            finally:
                self.mod.home = original  # type: ignore
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0].session_id, "abc")

    def test_discover_cursor_dotted_cwd_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / ".cursor" / "projects"
            project = root / self.mod.encode_cursor_cwd(
                str(tmp_path / "github.com/x/y")
            )
            project.mkdir(parents=True)
            (project / "agent-transcripts" / "claude").mkdir(parents=True)
            session = project / "agent-transcripts" / "claude" / "def.jsonl"
            session.write_text("{}\n")
            original = self.mod.home
            self.mod.home = lambda: tmp_path  # type: ignore
            try:
                cands = self.mod.discover_cursor(
                    str(tmp_path / "github.com/x/y"), None
                )
            finally:
                self.mod.home = original  # type: ignore
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0].session_id, "def")

    def test_discover_opencode_by_slug_and_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "opencode.db"
            cwd = str(tmp_path / "ws")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE session (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    slug TEXT,
                    directory TEXT,
                    title TEXT,
                    version TEXT,
                    time_created INTEGER,
                    time_updated INTEGER
                );
                INSERT INTO session VALUES (
                    'ses_alpha', 'p1', 'clever-canyon', '/fake/project',
                    'Refactor auth service', '1.0', 1000, 2000
                );
                INSERT INTO session VALUES (
                    'ses_beta', 'p1', 'silent-stone', '/fake/project',
                    'Add OAuth tests', '1.0', 1500, 2500
                );
                """
            )
            conn.close()

            old_env = os.environ.get("OPENCODE_DB")
            os.environ["OPENCODE_DB"] = str(db_path)
            try:
                # 1. By exact slug
                by_slug = self.mod.discover_opencode(cwd, "clever-canyon")
                self.assertEqual(len(by_slug), 1)
                self.assertEqual(by_slug[0].session_id, "ses_alpha")

                # 2. By exact title
                by_title = self.mod.discover_opencode(cwd, "Refactor auth service")
                self.assertEqual(len(by_title), 1)
                self.assertEqual(by_title[0].session_id, "ses_alpha")

                # 3. By case-insensitive substring title
                by_partial_title = self.mod.discover_opencode(cwd, "refactor auth")
                self.assertEqual(len(by_partial_title), 1)
                self.assertEqual(by_partial_title[0].session_id, "ses_alpha")

                # 4. By id
                by_id = self.mod.discover_opencode(cwd, "ses_beta")
                self.assertEqual(len(by_id), 1)
                self.assertEqual(by_id[0].session_id, "ses_beta")
            finally:
                if old_env is None:
                    os.environ.pop("OPENCODE_DB", None)
                else:
                    os.environ["OPENCODE_DB"] = old_env

    def test_discover_opencode_legacy_schema_resilience(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "opencode.db"
            cwd = str(tmp_path / "ws")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE session (
                    id TEXT PRIMARY KEY,
                    directory TEXT,
                    time_created INTEGER
                );
                INSERT INTO session VALUES ('ses_legacy', '/fake/project', 1000);
                """
            )
            conn.close()

            old_env = os.environ.get("OPENCODE_DB")
            os.environ["OPENCODE_DB"] = str(db_path)
            try:
                # Querying by id still works on legacy schemas lacking slug/title columns
                res = self.mod.discover_opencode(cwd, "ses_legacy")
                self.assertEqual(len(res), 1)
                self.assertEqual(res[0].session_id, "ses_legacy")

                # Querying by nonexistent slug/title returns empty instead of crashing
                res_slug = self.mod.discover_opencode(cwd, "nonexistent-slug")
                self.assertEqual(len(res_slug), 0)
            finally:
                if old_env is None:
                    os.environ.pop("OPENCODE_DB", None)
                else:
                    os.environ["OPENCODE_DB"] = old_env

    def test_pi_sibling_prefers_exact_id_over_newer_prefix_decoy(self):
        sid = "aaaaaaaa-bbbb-cccc"
        decoy = sid + "zz"
        cwd = "/Users/x/proj"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            sess = (
                home
                / ".pi"
                / "agent"
                / "sessions"
                / self.mod.encode_pi_cwd(cwd)
            )
            sess.mkdir(parents=True)
            exact = sess / f"20260101T120000_{sid}.jsonl"
            decoy_path = sess / f"20260101T130000_{decoy}.jsonl"
            for path, session_id, prompt in (
                (exact, sid, "exact prompt"),
                (decoy_path, decoy, "decoy prompt"),
            ):
                path.write_text(
                    json.dumps(
                        {"type": "session", "id": session_id, "cwd": cwd}
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "type": "message",
                            "message": {
                                "role": "user",
                                "content": prompt,
                            },
                        }
                    )
                    + "\n"
                )
            os.utime(exact, (1_700_000_000, 1_700_000_000))
            os.utime(decoy_path, (1_700_003_600, 1_700_003_600))

            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            try:
                code, out = self._main_output(
                    ["--cwd", cwd, "--agent", "pi", sid]
                )
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

            self.assertEqual(code, 0)
            self.assertIn(f"session_id: {sid}", out)
            self.assertNotIn(f"session_id: {decoy}", out)
            self.assertIn("exact prompt", out)
            self.assertNotIn("decoy prompt", out)

    def test_discover_codex_honors_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            custom_codex = tmp_path / "custom_codex"
            sessions_dir = (
                custom_codex / "sessions" / "2026" / "01" / "01"
            )
            sessions_dir.mkdir(parents=True)
            rollout = sessions_dir / (
                "rollout-2026-01-01T00-00-00-custom.jsonl"
            )
            self._write_codex_rollout(rollout)
            index_file = custom_codex / "session_index.jsonl"
            index_file.write_text(
                json.dumps(
                    {"id": "custom", "thread_name": "Custom Thread"}
                )
                + "\n"
            )

            old_codex = os.environ.get("CODEX_HOME")
            try:
                os.environ["CODEX_HOME"] = str(custom_codex)
                candidates = self.mod.discover_codex("/ws", "Custom Thread")
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0].agent, "codex")
                self.assertEqual(candidates[0].path, str(rollout))

                candidates_all = self.mod.discover_codex("/ws", None)
                self.assertEqual(len(candidates_all), 1)
                self.assertEqual(candidates_all[0].path, str(rollout))
            finally:
                if old_codex is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = old_codex

    def test_discover_claude_honors_claude_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            custom_claude = tmp_path / "custom_claude"
            project_dir = custom_claude / "projects" / "-ws"
            project_dir.mkdir(parents=True)
            session_file = project_dir / "custom-session.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "cwd": "/ws",
                        "sessionId": "custom-session",
                        "message": {"content": [{"type": "text", "text": "custom prompt"}]},
                    }
                )
                + "\n"
            )

            old_claude = os.environ.get("CLAUDE_CONFIG_DIR")
            try:
                os.environ["CLAUDE_CONFIG_DIR"] = str(custom_claude)
                candidates = self.mod.discover_claude("/ws", None)
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0].agent, "claude")
                self.assertEqual(candidates[0].path, str(session_file))

                candidates_by_id = self.mod.discover_claude("/ws", "custom-session")
                self.assertEqual(len(candidates_by_id), 1)
                self.assertEqual(candidates_by_id[0].path, str(session_file))
            finally:
                if old_claude is None:
                    os.environ.pop("CLAUDE_CONFIG_DIR", None)
                else:
                    os.environ["CLAUDE_CONFIG_DIR"] = old_claude

    def test_probed_roots_honors_custom_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            custom_codex = tmp_path / "custom_codex"
            custom_claude = tmp_path / "custom_claude"

            old_codex = os.environ.get("CODEX_HOME")
            old_claude = os.environ.get("CLAUDE_CONFIG_DIR")
            try:
                os.environ["CODEX_HOME"] = str(custom_codex)
                os.environ["CLAUDE_CONFIG_DIR"] = str(custom_claude)

                code, out = self._main_output(
                    ["--cwd", "/nonexistent", "--agent", "codex", "--list"]
                )
                self.assertIn(f"Probed: {custom_codex}/sessions", out)

                code, out = self._main_output(
                    ["--cwd", "/nonexistent", "--agent", "claude", "--list"]
                )
                self.assertIn(f"Probed: {custom_claude}/projects", out)
            finally:
                if old_codex is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = old_codex
                if old_claude is None:
                    os.environ.pop("CLAUDE_CONFIG_DIR", None)
                else:
                    os.environ["CLAUDE_CONFIG_DIR"] = old_claude


if __name__ == "__main__":
    unittest.main()
