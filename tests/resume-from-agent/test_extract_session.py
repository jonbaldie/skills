#!/usr/bin/env python3
"""Unit tests for resume-from-agent extract-session.py (temp fixtures only)."""

from __future__ import annotations

import json
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import isolated_env, load_skill_script


class ExtractSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_skill_script("resume-from-agent", "extract-session.py")

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

    def test_path_pi_transcript_with_and_without_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd_path = Path(tmp) / "project"
            cwd_path.mkdir()
            cwd = str(cwd_path)
            home = Path(tmp) / "home"
            path = (
                home
                / ".pi"
                / "agent"
                / "sessions"
                / self.mod.encode_pi_cwd(cwd)
                / "2026-10-03T00-00-00-000Z_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jsonl"
            )
            path.parent.mkdir(parents=True)
            records = [
                {
                    "type": "session",
                    "version": 3,
                    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "timestamp": "2026-10-03T00:00:00.000Z",
                    "cwd": cwd,
                },
                {
                    "type": "message",
                    "id": "1",
                    "parentId": None,
                    "timestamp": "2026-10-03T00:00:01.000Z",
                    "message": {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Fix the failing login test"}
                        ],
                    },
                },
                {
                    "type": "message",
                    "id": "2",
                    "parentId": "1",
                    "timestamp": "2026-10-03T00:00:02.000Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Reading tests/test_login.py first."}
                        ],
                        "stopReason": "stop",
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n")

            with patch.object(self.mod, "home", return_value=home), patch.dict(
                os.environ, {"HOME": str(home)}
            ):
                discovery_code, discovery = self._main_output(
                    ["--cwd", cwd, "--agent", "pi"]
                )
                self.assertEqual(discovery_code, 0)
                for agent_args in ([], ["--agent", "pi"]):
                    with self.subTest(agent_args=agent_args):
                        code, out = self._main_output(
                            [*agent_args, "--path", str(path)]
                        )
                        self.assertEqual(code, 0)
                        self.assertEqual(out, discovery)
                        self.assertIn("agent: pi", out)
                        self.assertIn(
                            "session_id: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", out
                        )
                        self.assertIn(f"cwd: {cwd}", out)
                        self.assertIn("Fix the failing login test", out)
                        self.assertIn("Reading tests/test_login.py first.", out)

    def test_path_codex_transcript_with_and_without_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd_path = Path(tmp) / "project"
            cwd_path.mkdir()
            cwd = str(cwd_path)
            codex_home = Path(tmp) / "codex"
            path = codex_home / "sessions" / "2026" / "10" / "03" / (
                "rollout-2026-10-03T00-00-00-11111111-2222-3333-4444-555555555555.jsonl"
            )
            path.parent.mkdir(parents=True)
            records = [
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "cwd": cwd,
                        "cli_version": "0.160.0",
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "user_message",
                        "message": "Create f01.txt through f12.txt",
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "phase": "commentary",
                        "message": "I will create each file with a separate apply_patch call.",
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n")

            with patch.dict(
                os.environ,
                {"HOME": str(Path(tmp) / "home"), "CODEX_HOME": str(codex_home)},
            ):
                discovery_code, discovery = self._main_output(
                    ["--cwd", cwd, "--agent", "codex"]
                )
                self.assertEqual(discovery_code, 0)
                for agent_args in ([], ["--agent", "codex"]):
                    with self.subTest(agent_args=agent_args):
                        code, out = self._main_output(
                            [*agent_args, "--path", str(path)]
                        )
                        self.assertEqual(code, 0)
                        self.assertEqual(out, discovery)
                        self.assertIn("agent: codex", out)
                        self.assertIn(
                            "session_id: 11111111-2222-3333-4444-555555555555", out
                        )
                        self.assertIn(f"cwd: {cwd}", out)
                        self.assertIn("Create f01.txt through f12.txt", out)
                        self.assertIn(
                            "I will create each file with a separate apply_patch call.",
                            out,
                        )

    def test_path_without_agent_rejects_unidentifiable_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unknown.jsonl"
            path.write_text(json.dumps({"type": "not-a-session", "value": 1}) + "\n")

            code, _ = self._main_output(["--path", str(path)])

            self.assertIsInstance(code, SystemExit)
            self.assertIn("Could not identify", str(code))
            self.assertIn(str(path), str(code))

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

    def test_path_agent_codex_records_turn_aborted_ending(self):
        with tempfile.TemporaryDirectory() as tmp:
            rollout = Path(tmp) / "rollout-xyz.jsonl"
            lines = [
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:00Z",
                        "type": "session_meta",
                        "payload": {"id": "rollout-xyz", "cwd": "/ws"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:01Z",
                        "type": "event_msg",
                        "payload": {"type": "user_message", "message": "Create files"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:02Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "agent_message",
                            "phase": "commentary",
                            "message": "I will create files.",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:03Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "turn_aborted",
                            "turn_id": "t1",
                            "reason": "interrupted",
                        },
                    }
                ),
            ]
            rollout.write_text("\n".join(lines) + "\n")
            code, out = self._main_output(
                ["--agent", "codex", "--path", str(rollout)]
            )
            self.assertEqual(code, 0)
            self.assertIn("agent: codex", out)
            self.assertIn("## Ending\nturn_aborted: interrupted", out)

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

    def test_path_no_agent_identifies_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            self._write_hermes_db(db_path)
            code, out = self._main_output(["--path", str(db_path)])
            self.assertEqual(code, 0)
            self.assertIn("agent: hermes", out)
            self.assertIn("session_id: sess_abc", out)
            self.assertIn("Implement resume-from-agent", out)

    def test_malformed_database_schemas_report_missing_columns(self):
        script = Path(self.mod.__file__)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for table, column in (("sessions", "end_reason"), ("messages", "finish_reason")):
                db = root / f"hermes-{table}.db"
                self._write_hermes_db(db)
                with sqlite3.connect(db) as conn:
                    conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
                for agent_args in ([], ["--agent", "hermes"]):
                    with self.subTest(table=table, agent_args=agent_args):
                        proc = subprocess.run(
                            [sys.executable, str(script), *agent_args, "--path", str(db)],
                            capture_output=True, text=True,
                        )
                        self.assertNotEqual(proc.returncode, 0)
                        self.assertEqual(proc.stdout, "")
                        self.assertIn(str(db), proc.stderr)
                        self.assertIn("hermes", proc.stderr.lower())
                        self.assertIn(table, proc.stderr)
                        self.assertIn(column, proc.stderr)
                        self.assertNotIn("Traceback", proc.stderr)

            db = root / "opencode.db"
            with sqlite3.connect(db) as conn:
                conn.executescript("""
                    CREATE TABLE session (id TEXT, time_created INTEGER);
                    INSERT INTO session VALUES ('s1', 1);
                    CREATE TABLE message (id TEXT);
                    CREATE TABLE part (id TEXT);
                """)
            for agent_args in ([], ["--agent", "opencode"]):
                with self.subTest(agent_args=agent_args):
                    proc = subprocess.run(
                        [sys.executable, str(script), *agent_args, "--path", str(db)],
                        capture_output=True, text=True,
                    )
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(proc.stdout, "")
                    self.assertIn(str(db), proc.stderr)
                    self.assertIn("opencode", proc.stderr.lower())
                    self.assertIn("message", proc.stderr)
                    self.assertIn("session_id", proc.stderr)
                    self.assertNotIn("Traceback", proc.stderr)

    def test_path_large_first_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude = root / "large.jsonl"
            claude.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "large goal", "image": "x" * 2_100_000}}))
            for args in ([], ["--agent", "claude"]):
                code, out = self._main_output([*args, "--path", str(claude)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("large goal", out)

    def test_path_headerless_gemini_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            gemini = Path(tmp) / "gemini.jsonl"
            gemini.write_text('\n'.join(map(json.dumps, [{"type": "user", "content": "gemini goal"}, {"type": "gemini", "content": "gemini answer"}])))
            code, out = self._main_output(["--agent", "gemini", "--path", str(gemini)])
            self.assertEqual(code, 0, str(code))
            self.assertIn("gemini goal", out)

    def test_path_malformed_probe_fields_do_not_mask_pi(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pi.jsonl"
            path.write_text('\n'.join(map(json.dumps, [{"type": [], "role": {}}, {"type": "session", "id": "pi-id"}, {"type": "message", "message": {"role": "user", "content": "pi goal"}}])))
            code, out = self._main_output(["--path", str(path)])
            self.assertEqual(code, 0, str(code))
            self.assertIn("pi goal", out)

    def test_cli_symlink_reads_committed_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            self._write_hermes_db(db)
            writer = sqlite3.connect(db)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("UPDATE messages SET content='committed WAL goal' WHERE role='user'")
                writer.commit()
                alias = Path(tmp) / "alias.db"
                alias.symlink_to(db)
                before = {p.name: p.read_bytes() for p in Path(tmp).iterdir()}
                for args in ([], ["--agent", "hermes"]):
                    result = self._run_cli(alias, args)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("committed WAL goal", result.stdout)
                    self.assertEqual(before, {p.name: p.read_bytes() for p in Path(tmp).iterdir()})
            finally:
                writer.close()

    def test_cli_rejects_spilled_uncommitted_rollback_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            self._write_hermes_db(db)
            writer = sqlite3.connect(db)
            try:
                writer.execute("PRAGMA journal_mode=DELETE")
                writer.execute("PRAGMA cache_size=2")
                writer.execute("CREATE TABLE padding(id INTEGER PRIMARY KEY, data BLOB)")
                writer.executemany("INSERT INTO padding VALUES (?, ?)", [(i, b'A' * 4096) for i in range(100)])
                writer.commit()
                writer.execute("UPDATE messages SET content='UNCOMMITTED PHANTOM GOAL' WHERE role='user'")
                writer.execute("UPDATE padding SET data=?", (b'B' * 4096,))
                self.assertIn(b'UNCOMMITTED PHANTOM GOAL', db.read_bytes())
                before = {p.name: p.read_bytes() for p in Path(tmp).iterdir()}
                for args in ([], ["--agent", "hermes"]):
                    result = self._run_cli(db, args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Could not safely read", result.stderr)
                    self.assertNotIn("UNCOMMITTED PHANTOM GOAL", result.stdout)
                    self.assertEqual(before, {p.name: p.read_bytes() for p in Path(tmp).iterdir()})
                writer.rollback()
                self.assertEqual(writer.execute("SELECT content FROM messages WHERE role='user'").fetchone()[0], "Implement resume-from-agent")
            finally:
                writer.close()

    def test_cli_malformed_records_do_not_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = [
                ("gemini.json", {"sessionId": "g", "messages": [None]}, "gemini"),
                ("gemini-type.json", {"sessionId": "g", "messages": [{"type": [], "content": "goal"}]}, "gemini"),
                ("claude.jsonl", [{"type": [], "role": {}}, {"type": "user", "message": {"role": "user", "content": "goal"}}], "claude"),
            ]
            for name, content, agent in cases:
                path = Path(tmp) / name
                path.write_text("\n".join(map(json.dumps, content)) if isinstance(content, list) else json.dumps(content))
                for args in ([], ["--agent", agent]):
                    result = self._run_cli(path, args)
                    self.assertNotIn("Traceback", result.stderr, (name, result.stderr))
                    if result.returncode:
                        self.assertIn("Could not", result.stderr)
                    else:
                        self.assertIn("goal", result.stdout)

    def _run_cli(self, path, args):
        script = Path(__file__).resolve().parents[2] / "skills/resume-from-agent/scripts/extract-session.py"
        return subprocess.run([sys.executable, str(script), "--path", str(path), *args], capture_output=True, text=True)

    def test_path_wal_snapshot_has_no_source_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "state.db"
            self._write_hermes_db(db)
            writer = sqlite3.connect(db)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("live", "live", "/ws", "model", 1800000000, None, 1, None, None, "cli", 1))
            writer.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)", (100, "live", "user", "live WAL goal", None, None, 1800000000, None, 1))
            writer.commit()
            def snapshot():
                return {p.name: p.read_bytes() for p in root.iterdir()}
            before = snapshot()
            for args in ([], ["--agent", "hermes"]):
                code, out = self._main_output([*args, "--path", str(db)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("session_id: live", out)
                self.assertIn("live WAL goal", out)
                self.assertEqual(snapshot(), before)
            writer.close()
            before = snapshot()
            code, out = self._main_output(["--path", str(db)])
            self.assertEqual(code, 0, str(code))
            self.assertIn("live WAL goal", out)
            self.assertEqual(snapshot(), before)

    def test_cli_accepts_inactive_retained_journals(self):
        for mode in ("PERSIST", "TRUNCATE"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                db = root / "state.db"
                self._write_hermes_db(db)
                writer = sqlite3.connect(db)
                try:
                    self.assertEqual(writer.execute(f"PRAGMA journal_mode={mode}").fetchone()[0].upper(), mode)
                    writer.execute("UPDATE messages SET content='retained journal goal' WHERE role='user'")
                    writer.commit()
                finally:
                    writer.close()
                journal = Path(str(db) + "-journal")
                self.assertTrue(journal.exists())
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                for args in ([], ["--agent", "hermes"]):
                    result = self._run_cli(db, args)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("retained journal goal", result.stdout)
                    self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_autodetect_json_without_fcntl_and_reject_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claude.jsonl"
            path.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "json goal"}}))
            db = Path(tmp) / "state.db"
            self._write_hermes_db(db)
            with patch.object(self.mod, "fcntl", None):
                code, out = self._main_output(["--path", str(path)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("json goal", out)
                code, out = self._main_output(["--path", str(db)])
                self.assertIsInstance(code, SystemExit)
                self.assertIn("Cannot safely lock", str(code))
                self.assertFalse(out)

    def test_snapshot_rejects_nonzero_or_changing_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            self._write_hermes_db(db)
            journal = Path(str(db) + "-journal")
            journal.write_bytes(b"\xd9\xd5\x05\xf9\x20\xa1\x63\xd7" + bytes(504))
            with self.assertRaisesRegex(self.mod.UnsafeSnapshotError, "Rollback journal"):
                self.mod.open_sqlite_ro(db)
            journal.write_bytes(bytes(512))
            real_copy = self.mod.shutil.copyfileobj

            def change_journal(source, target):
                real_copy(source, target)
                journal.write_bytes(bytes(513))

            with patch.object(self.mod.shutil, "copyfileobj", side_effect=change_journal):
                with self.assertRaisesRegex(self.mod.UnsafeSnapshotError, "Rollback journal changed"):
                    self.mod.open_sqlite_ro(db)

    def test_unknown_checkpointed_wal_does_not_create_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "unknown.db"
            conn = sqlite3.connect(db)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE unrelated (id TEXT)")
            conn.commit()
            conn.close()
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            for args in ([], ["--agent", "hermes"]):
                code, out = self._main_output([*args, "--path", str(db)])
                self.assertIsInstance(code, SystemExit)
                self.assertFalse(out)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_sqlite_snapshot_rejects_continuous_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            self._write_hermes_db(db)
            real_copy = self.mod.shutil.copyfileobj
            def changing_copy(source, target):
                real_copy(source, target)
                os.utime(db, None)
            with patch.object(self.mod.shutil, "copyfileobj", side_effect=changing_copy):
                with self.assertRaisesRegex(sqlite3.OperationalError, "changed while copying"):
                    self.mod.open_sqlite_ro(db)

    def test_sqlite_snapshot_rejects_journal_created_during_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            self._write_hermes_db(db)
            writer_code = (
                "import sqlite3, sys\n"
                "conn = sqlite3.connect(sys.argv[1])\n"
                "conn.execute(\"UPDATE messages SET content='pending' WHERE role='user'\")\n"
                "print('ready', flush=True)\n"
                "sys.stdin.readline()\n"
                "conn.rollback()\n"
            )
            writer = None
            real_copy = self.mod.shutil.copyfileobj

            def start_writer(source, target):
                nonlocal writer
                writer = subprocess.Popen([sys.executable, "-c", writer_code, str(db)],
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                self.assertEqual(writer.stdout.readline().strip(), "ready")
                self.assertTrue(Path(str(db) + "-journal").exists())
                real_copy(source, target)

            try:
                with patch.object(self.mod.shutil, "copyfileobj", side_effect=start_writer):
                    with self.assertRaisesRegex(sqlite3.OperationalError, "Rollback journal"):
                        self.mod.open_sqlite_ro(db)
            finally:
                if writer:
                    writer.communicate("done\n", timeout=5)

    def test_opencode_live_wal_does_not_change_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "opencode.db"
            writer = sqlite3.connect(db)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.executescript("""
                CREATE TABLE session (id TEXT, title TEXT, directory TEXT, path TEXT, agent TEXT, version TEXT, time_updated INTEGER, time_created INTEGER, time_archived INTEGER, model TEXT, slug TEXT);
                CREATE TABLE todo (session_id TEXT, content TEXT, status TEXT, priority TEXT, position INTEGER);
                CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
                CREATE TABLE part (id TEXT, session_id TEXT, message_id TEXT, time_created INTEGER, data TEXT);
            """)
            writer.execute("INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("live", "live", "/ws", "/ws", None, None, 2, 2, None, None, None))
            writer.execute("INSERT INTO message VALUES (?, ?, ?, ?)", ("m", "live", 2, json.dumps({"role": "user"})))
            writer.execute("INSERT INTO part VALUES (?, ?, ?, ?, ?)", ("p", "live", "m", 2, json.dumps({"type": "text", "text": "opencode WAL goal"})))
            writer.commit()
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            for args in ([], ["--agent", "opencode"]):
                code, out = self._main_output([*args, "--path", str(db)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("opencode WAL goal", out)
                self.assertIn(str(db), out)
                self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)
            writer.close()

    def test_path_identifies_transcript_formats(self):
        fixtures = {
            "claude": [{"type": "user", "sessionId": "real-session", "cwd": "/ws", "uuid": "uuid-1", "message": {"role": "user", "content": "Shared goal"}}, {"type": "assistant", "sessionId": "real-session", "cwd": "/ws", "uuid": "uuid-2", "message": {"role": "assistant", "content": "Shared reply"}}],
            "cursor": [{"role": "user", "message": {"content": [{"type": "text", "text": "Shared goal"}]}}, {"role": "assistant", "message": {"content": [{"type": "text", "text": "Shared reply"}]}}, {"type": "turn_ended", "status": "completed"}],
            "goose": [{"working_dir": "/ws"}, {"role": "user", "content": [{"type": "text", "text": "Shared goal"}]}, {"role": "assistant", "content": [{"type": "text", "text": "Shared reply"}]}],
            "gemini": {"sessionId": "gem-1", "messages": [{"type": "user", "content": "Shared goal"}, {"type": "gemini", "content": "Shared reply"}]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            for agent, records in fixtures.items():
                with self.subTest(agent=agent):
                    path = Path(tmp) / (agent + (".json" if agent == "gemini" else ".jsonl"))
                    path.write_text(json.dumps(records) if isinstance(records, dict) else "\n".join(map(json.dumps, records)))
                    automatic, out = self._main_output(["--path", str(path)])
                    explicit, expected = self._main_output(["--agent", agent, "--path", str(path)])
                    self.assertEqual(explicit, 0)
                    self.assertEqual(automatic, 0, str(automatic))
                    self.assertEqual(out, expected)
                    self.assertIn("agent: " + agent, out)
                    self.assertIn("Shared goal", out)
                    self.assertIn("Shared reply", out)

    def test_path_database_selection_and_no_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            self._write_hermes_db(path)
            conn = sqlite3.connect(path)
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("older", "old", "/ws", "model", 1, 2, 1, None, None, "cli", 1))
            conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)", (3, "older", "user", "old message", None, None, 1, None, 1))
            conn.commit(); conn.close()
            before = path.read_bytes()
            for args in ([], ["--agent", "hermes"]):
                code, out = self._main_output([*args, "--path", str(path)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("session_id: sess_abc", out)
                self.assertIn("Implement resume-from-agent", out)
                self.assertNotIn("old message", out)
                self.assertEqual(path.read_bytes(), before)

    def test_path_opencode_latest_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.db"
            conn = sqlite3.connect(path)
            conn.executescript("""
                CREATE TABLE session (id TEXT, title TEXT, directory TEXT, path TEXT, agent TEXT, version TEXT, time_updated INTEGER, time_created INTEGER, time_archived INTEGER, model TEXT, slug TEXT);
                CREATE TABLE todo (session_id TEXT, content TEXT, status TEXT, priority TEXT, position INTEGER);
                CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
                CREATE TABLE part (id TEXT, session_id TEXT, message_id TEXT, time_created INTEGER, data TEXT);
            """)
            for sid, timestamp, message in [("old", 1, "old goal"), ("new", 2, "new goal")]:
                conn.execute("INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (sid, sid, "/ws", "/ws", None, None, timestamp, timestamp, None, None, None))
                conn.execute("INSERT INTO message VALUES (?, ?, ?, ?)", (sid, sid, timestamp, json.dumps({"role": "user"})))
                conn.execute("INSERT INTO part VALUES (?, ?, ?, ?, ?)", (sid, sid, sid, timestamp, json.dumps({"type": "text", "text": message})))
            conn.execute("INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("archived", "archived", "/ws", "/ws", None, None, 3, 3, 4, None, None))
            conn.commit(); conn.close()
            before = path.read_bytes()
            for args in ([], ["--agent", "opencode"]):
                code, out = self._main_output([*args, "--path", str(path)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("agent: opencode", out)
                self.assertIn("session_id: new", out)
                self.assertIn("new goal", out)
                self.assertNotIn("old goal", out)
                self.assertEqual(path.read_bytes(), before)

    def test_path_unknown_mismatched_ambiguous_and_agy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.db"
            conn = sqlite3.connect(path); conn.execute("CREATE TABLE unrelated (id TEXT)"); conn.commit(); conn.close()
            before = path.read_bytes()
            for args in ([], ["--agent", "agy"], ["--agent", "hermes"]):
                code, out = self._main_output([*args, "--path", str(path)])
                self.assertIsInstance(code, SystemExit)
                self.assertFalse(out)
                self.assertEqual(before, path.read_bytes())
            conn = sqlite3.connect(path)
            conn.executescript("CREATE TABLE session (id TEXT); CREATE TABLE message (id TEXT); CREATE TABLE part (id TEXT); CREATE TABLE steps (idx INTEGER, step_payload BLOB, task_details BLOB, render_info BLOB);")
            conn.commit(); conn.close()
            before = path.read_bytes()
            code, out = self._main_output(["--path", str(path)])
            self.assertIsInstance(code, SystemExit)
            self.assertIn("Ambiguous", str(code))
            self.assertFalse(out)
            self.assertEqual(before, path.read_bytes())
            conn = sqlite3.connect(path); conn.execute("DROP TABLE session"); conn.execute("INSERT INTO steps VALUES (1, ?, NULL, NULL)", (b"This is a sufficiently long real transcript message for the AGY extractor.",)); conn.commit(); conn.close()
            before = path.read_bytes()
            code, out = self._main_output(["--path", str(path)])
            self.assertEqual(code, 0, str(code))
            self.assertIn("agent: agy", out)
            self.assertEqual(before, path.read_bytes())
            path.write_text('{"type":"user", "message":')
            for args in ([], ["--agent", "claude"]):
                code, out = self._main_output([*args, "--path", str(path)])
                self.assertIsInstance(code, SystemExit)
                self.assertFalse(out)

    def test_path_regressions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude = root / "claude.jsonl"
            claude.write_text(json.dumps({"type": "user", "sessionId": "id", "message": {"role": "user", "content": "real goal"}}) + '\n{"unfinished":')
            for args in ([], ["--agent", "claude"]):
                code, out = self._main_output([*args, "--path", str(claude)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("real goal", out)
            code, _ = self._main_output(["--agent", "gemini", "--path", str(claude)])
            self.assertIsInstance(code, SystemExit)
            task = root / "task"
            task.mkdir()
            (task / "ui_messages.json").write_text(json.dumps([{"say": "task", "text": "dirac goal"}]))
            code, out = self._main_output(["--agent", "dirac", "--path", str(task)])
            self.assertEqual(code, 0, str(code))
            self.assertIn("dirac goal", out)
            fixtures = {
                "gemini": (".json", [{"type": "user", "content": "legacy goal"}]),
                "goose": (".jsonl", [{"role": "user", "content": [{"type": "text", "text": "legacy goal"}]}]),
                "cursor": (".jsonl", [{"role": "user", "message": {"content": [{"type": "text", "text": "legacy goal"}]}}]),
            }
            for agent, (suffix, records) in fixtures.items():
                with self.subTest(agent=agent):
                    path = root / (agent + suffix)
                    path.write_text(json.dumps(records) if suffix == ".json" else "\n".join(map(json.dumps, records)))
                    code, out = self._main_output(["--agent", agent, "--path", str(path)])
                    self.assertEqual(code, 0, str(code))
                    self.assertIn("legacy goal", out)
                    code, _ = self._main_output(["--path", str(path)])
                    self.assertIsInstance(code, SystemExit)

    def test_path_probe_bounded_and_sqlite_schemas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "large.jsonl"
            path.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "goal"}}) + "\n" + " " * 4_000_000)
            with patch.object(Path, "read_text", side_effect=AssertionError("unbounded read")):
                self.assertTrue(self.mod.ADAPTERS["claude"].identify(path))
            for schema in ("CREATE TABLE session (id TEXT, time_created INTEGER)", "CREATE TABLE steps (id INTEGER)"):
                path = root / (str(len(schema)) + ".db")
                conn = sqlite3.connect(path); conn.execute(schema); conn.close()
                code, out = self._main_output(["--path", str(path)])
                self.assertIsInstance(code, SystemExit)
                self.assertFalse(out)

    def test_json_probe_reads_a_bounded_prefix_once(self):
        payload = (json.dumps({"type": "user", "message": {"role": "user", "content": "goal"}}) + "\n").encode() + b" " * 4_000_000
        class TrackedStream(io.BytesIO):
            def read(self, size=-1):
                self_test.assertGreater(size, 0)
                self_test.assertLessEqual(size, 2_000_001)
                return super().read(size)
        self_test = self
        path = Path("large.jsonl")
        self.mod._json_values.cache_clear()
        try:
            with patch.object(Path, "open", side_effect=lambda *args, **kwargs: TrackedStream(payload)) as opened:
                self.assertTrue(self.mod.ADAPTERS["claude"].identify(path))
                self.assertFalse(self.mod.ADAPTERS["codex"].identify(path))
                self.assertEqual(opened.call_count, 1)
        finally:
            self.mod._json_values.cache_clear()

    def test_cursor_skips_malformed_and_non_object_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cursor.jsonl"
            path.write_text('\n'.join([
                'not json', '[]',
                json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "cursor goal"}]}}),
                json.dumps({"type": "turn_ended", "status": "completed"}),
                '{"unfinished":',
            ]))
            for args in ([], ["--agent", "cursor"]):
                code, out = self._main_output([*args, "--path", str(path)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("cursor goal", out)

    def test_registered_adapter_controls_path_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.fixture"
            path.write_text("custom")
            def candidate(p):
                return self.mod.Candidate(agent="test", session_id="custom-id", cwd=None, mtime=0, path=str(p))
            def extract(c):
                return self.mod.Brief(agent=c.agent, session_id=c.session_id, path=c.path, opening_users=["custom goal"])
            adapter = self.mod.Adapter(name="test", aliases=(), discover=lambda cwd, sid: [], extract=extract, roots=(), identify=lambda p: p.read_text() == "custom", candidate_from_path=candidate)
            with patch.dict(self.mod.ADAPTERS, {"test": adapter}):
                code, out = self._main_output(["--path", str(path)])
                self.assertEqual(code, 0, str(code))
                self.assertIn("session_id: custom-id", out)
                self.assertIn("custom goal", out)

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

            with isolated_env(OPENCODE_DB=str(db_path)):
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

            with isolated_env(OPENCODE_DB=str(db_path)):
                # Querying by id still works on legacy schemas lacking slug/title columns
                res = self.mod.discover_opencode(cwd, "ses_legacy")
                self.assertEqual(len(res), 1)
                self.assertEqual(res[0].session_id, "ses_legacy")

                # Querying by nonexistent slug/title returns empty instead of crashing
                res_slug = self.mod.discover_opencode(cwd, "nonexistent-slug")
                self.assertEqual(len(res_slug), 0)

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

            with isolated_env(HOME=str(home)):
                code, out = self._main_output(
                    ["--cwd", cwd, "--agent", "pi", sid]
                )

            self.assertEqual(code, 0)
            self.assertIn(f"session_id: {sid}", out)
            self.assertNotIn(f"session_id: {decoy}", out)
            self.assertIn("exact prompt", out)
            self.assertNotIn("decoy prompt", out)

    def _write_pi_exact_and_decoy(self, home: Path, cwd: str):
        """An older exact-id Pi session and a newer id-prefix decoy (#175)."""
        sess = (
            home / ".pi" / "agent" / "sessions" / self.mod.encode_pi_cwd(cwd)
        )
        sess.mkdir(parents=True)
        exact = sess / "2026-01-01T12-00-00-000Z_7f3a.jsonl"
        decoy = sess / "2026-01-01T13-00-00-000Z_7f3a99b2.jsonl"
        for path, session_id, prompt in (
            (exact, "7f3a", "exact prompt"),
            (decoy, "7f3a99b2", "decoy prompt"),
        ):
            path.write_text(
                json.dumps({"type": "session", "id": session_id, "cwd": cwd})
                + "\n"
                + json.dumps(
                    {
                        "type": "message",
                        "message": {"role": "user", "content": prompt},
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "message",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": f"reply to {prompt}"}
                            ],
                        },
                    }
                )
                + "\n"
            )
        os.utime(exact, (1_700_000_000, 1_700_000_000))
        os.utime(decoy, (1_700_003_600, 1_700_003_600))
        return exact, decoy

    def test_pi_brief_matches_selected_candidate_with_or_without_sibling(self):
        cwd = "/work/proj"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            exact, decoy = self._write_pi_exact_and_decoy(home, cwd)
            sibling = self.mod.find_sibling_extractor
            self.assertIsNotNone(sibling("pi"))
            for label, finder in (
                ("sibling", sibling),
                ("standalone", lambda agent: None),
            ):
                with self.subTest(label), patch.dict(
                    os.environ, {"HOME": str(home)}
                ), patch.object(self.mod, "find_sibling_extractor", finder):
                    code, out = self._main_output(["--cwd", cwd, "pi", "7f3a"])
                    self.assertEqual(code, 0)
                    self.assertIn(f"path: {exact}\n", out)
                    self.assertNotIn(str(decoy), out)
                    self.assertIn("session_id: 7f3a\n", out)
                    self.assertNotIn("decoy prompt", out)
                    self.assertIn("exact prompt", out)
                    self.assertIn("reply to exact prompt", out)

    def test_pi_list_shows_each_sessions_real_id_exact_first(self):
        cwd = "/work/proj"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            exact, decoy = self._write_pi_exact_and_decoy(home, cwd)
            with patch.dict(os.environ, {"HOME": str(home)}):
                code, out = self._main_output(
                    ["--cwd", cwd, "--list", "pi", "7f3a"]
                )
        self.assertEqual(code, 0)
        rows = [line for line in out.splitlines() if line[:1].isdigit()]
        self.assertEqual(len(rows), 2)
        self.assertIn("id=7f3a ", rows[0])
        self.assertIn(f"path={exact}", rows[0])
        self.assertIn("id=7f3a99b2 ", rows[1])
        self.assertIn(f"path={decoy}", rows[1])

    def _write_pi_colliding_projects(self, tmp: Path):
        """Sessions for two cwds that encode to one Pi directory (#215)."""
        home = tmp / "home"
        mine = tmp / "apps" / "web-api"
        other = tmp / "apps-web" / "api"
        mine.mkdir(parents=True)
        other.mkdir(parents=True)
        key = self.mod.encode_pi_cwd(str(mine))
        self.assertEqual(key, self.mod.encode_pi_cwd(str(other)))
        sess = home / ".pi" / "agent" / "sessions" / key
        sess.mkdir(parents=True)
        own = sess / "2026-01-01T12-00-00-000Z_2222.jsonl"
        foreign = sess / "2026-01-01T13-00-00-000Z_3333.jsonl"
        for path, session_id, cwd, prompt in (
            (own, "2222", mine, "own project goal"),
            (foreign, "3333", other, "other project goal"),
        ):
            path.write_text(
                json.dumps(
                    {"type": "session", "version": 3, "id": session_id, "cwd": str(cwd)}
                )
                + "\n"
                + json.dumps(
                    {"type": "message", "message": {"role": "user", "content": prompt}}
                )
                + "\n"
            )
        os.utime(own, (1_700_000_000, 1_700_000_000))
        os.utime(foreign, (1_700_003_600, 1_700_003_600))
        return home, mine, other, own, foreign

    def test_pi_colliding_cwd_selects_own_session_with_or_without_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, mine, other, own, foreign = self._write_pi_colliding_projects(
                Path(tmp)
            )
            sibling = self.mod.find_sibling_extractor
            self.assertIsNotNone(sibling("pi"))
            for label, finder in (
                ("sibling", sibling),
                ("standalone", lambda agent: None),
            ):
                with self.subTest(label), patch.dict(
                    os.environ, {"HOME": str(home)}
                ), patch.object(self.mod, "find_sibling_extractor", finder):
                    code, out = self._main_output(["--cwd", str(mine), "pi"])
                    self.assertEqual(code, 0)
                    self.assertIn("session_id: 2222\n", out)
                    self.assertIn(f"cwd: {mine}\n", out)
                    self.assertIn("own project goal", out)
                    self.assertNotIn("other project goal", out)

                    code, out = self._main_output(
                        ["--cwd", str(mine), "--list", "pi"]
                    )
                    self.assertEqual(code, 0)
                    self.assertIn(f"path={own}", out)
                    self.assertNotIn(str(foreign), out)

                    # A pinned id may cross projects but reports its own cwd.
                    code, out = self._main_output(
                        ["--cwd", str(mine), "pi", "3333"]
                    )
                    self.assertEqual(code, 0)
                    self.assertIn("session_id: 3333\n", out)
                    self.assertIn(f"cwd: {other}\n", out)
                    self.assertNotIn(f"cwd: {mine}\n", out)
                    self.assertIn("other project goal", out)

    def test_pi_colliding_cwd_never_emits_only_other_project_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, mine, other, own, foreign = self._write_pi_colliding_projects(
                Path(tmp)
            )
            own.unlink()
            for label, finder in (
                ("sibling", self.mod.find_sibling_extractor),
                ("standalone", lambda agent: None),
            ):
                with self.subTest(label), patch.dict(
                    os.environ, {"HOME": str(home)}
                ), patch.object(self.mod, "find_sibling_extractor", finder):
                    code, out = self._main_output(["--cwd", str(mine), "pi"])
                    self.assertIsInstance(code, SystemExit)
                    self.assertNotIn("other project goal", out)
                    code, out = self._main_output(
                        ["--cwd", str(mine), "--list", "pi"]
                    )
                    self.assertEqual(code, 1)
                    self.assertNotIn(str(foreign), out)

    def test_rank_candidates_orders_by_match_tier_then_recency(self):
        C = self.mod.Candidate

        def cand(sid, match, mtime):
            return C(agent="x", session_id=sid, cwd=None, mtime=mtime, match=match)

        ranked = self.mod.rank_candidates(
            [
                cand("title-newest", "title", 600.0),
                cand("substring", "id-substring", 500.0),
                cand("prefix-new", "id-prefix", 400.0),
                cand("prefix-old", "id-prefix", 300.0),
                cand("exact", "exact", 100.0),
            ]
        )
        self.assertEqual(
            [c.session_id for c in ranked],
            ["exact", "prefix-new", "prefix-old", "substring", "title-newest"],
        )
        winner, notes = self.mod.pick_candidate(ranked)
        self.assertEqual(winner.session_id, "exact")
        self.assertTrue(any("exact" in n for n in notes))

    def test_rank_candidates_without_query_is_newest_first(self):
        C = self.mod.Candidate
        ranked = self.mod.rank_candidates(
            [
                C(agent="x", session_id="old", cwd=None, mtime=1.0),
                C(agent="x", session_id="new", cwd=None, mtime=2.0),
            ]
        )
        self.assertEqual([c.session_id for c in ranked], ["new", "old"])

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

            with isolated_env(CODEX_HOME=str(custom_codex)):
                candidates = self.mod.discover_codex("/ws", "Custom Thread")
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0].agent, "codex")
                self.assertEqual(candidates[0].path, str(rollout))

                candidates_all = self.mod.discover_codex("/ws", None)
                self.assertEqual(len(candidates_all), 1)
                self.assertEqual(candidates_all[0].path, str(rollout))

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

            with isolated_env(CLAUDE_CONFIG_DIR=str(custom_claude)):
                candidates = self.mod.discover_claude("/ws", None)
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0].agent, "claude")
                self.assertEqual(candidates[0].path, str(session_file))

                candidates_by_id = self.mod.discover_claude("/ws", "custom-session")
                self.assertEqual(len(candidates_by_id), 1)
                self.assertEqual(candidates_by_id[0].path, str(session_file))

    def test_probed_roots_honors_custom_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            custom_codex = tmp_path / "custom_codex"
            custom_claude = tmp_path / "custom_claude"

            with isolated_env(CODEX_HOME=str(custom_codex), CLAUDE_CONFIG_DIR=str(custom_claude)):
                code, out = self._main_output(
                    ["--cwd", "/nonexistent", "--agent", "codex", "--list"]
                )
                self.assertIn(f"Probed: {custom_codex}/sessions", out)

                code, out = self._main_output(
                    ["--cwd", "/nonexistent", "--agent", "claude", "--list"]
                )
                self.assertIn(f"Probed: {custom_claude}/projects", out)


if __name__ == "__main__":
    unittest.main()
