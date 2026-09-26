#!/usr/bin/env python3
"""Tests for resume-from-opencode extract-session.py (temp databases only)."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "resume-from-opencode" / "scripts" / "extract-session.py"

CWD = "/tmp/no-such-resume-cwd-141"


def load_mod():
    spec = importlib.util.spec_from_file_location(
        "extract_session_opencode", SCRIPT
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_session_opencode"] = mod
    spec.loader.exec_module(mod)
    return mod


def empty_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE session (
            id TEXT,
            directory TEXT,
            path TEXT,
            time_archived INTEGER,
            time_updated INTEGER,
            project_id TEXT,
            slug TEXT,
            title TEXT,
            agent TEXT,
            model TEXT,
            version TEXT,
            time_created INTEGER
        );
        CREATE TABLE project (id TEXT, worktree TEXT);
        """
    )
    conn.close()


def session_db(path: Path, cwd: str, session_id: str, prompt: str) -> None:
    empty_db(path)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE message (
            id TEXT,
            session_id TEXT,
            time_created INTEGER,
            data TEXT
        );
        CREATE TABLE part (
            id TEXT,
            message_id TEXT,
            session_id TEXT,
            time_created INTEGER,
            data TEXT
        );
        CREATE TABLE todo (
            content TEXT,
            status TEXT,
            priority TEXT,
            position INTEGER,
            session_id TEXT
        );
        CREATE TABLE session_message (
            type TEXT,
            data TEXT,
            time_created INTEGER,
            session_id TEXT,
            seq INTEGER
        );
        """
    )
    conn.execute(
        """
        INSERT INTO session (
            id, directory, path, time_updated, time_created, slug, title
        ) VALUES (?, ?, ?, 1, 1, 'clever-canyon', 'Resume work')
        """,
        (session_id, cwd, cwd),
    )
    conn.execute(
        """
        INSERT INTO message (id, session_id, time_created, data)
        VALUES ('msg1', ?, 1, ?)
        """,
        (session_id, json.dumps({"role": "user"})),
    )
    conn.execute(
        """
        INSERT INTO part (id, message_id, session_id, time_created, data)
        VALUES ('part1', 'msg1', ?, 1, ?)
        """,
        (
            session_id,
            json.dumps({"type": "text", "text": prompt}),
        ),
    )
    conn.commit()
    conn.close()


class NoSessionDatabasePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def setUp(self):
        self._old_home = os.environ.get("HOME")
        self._old_db = os.environ.get("OPENCODE_DB")
        os.environ.pop("OPENCODE_DB", None)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_db is None:
            os.environ.pop("OPENCODE_DB", None)
        else:
            os.environ["OPENCODE_DB"] = self._old_db

    def _no_session(self, argv: list[str]) -> str:
        with self.assertRaises(SystemExit) as caught:
            self.mod.main(argv)
        return str(caught.exception)

    def test_no_session_names_db_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "some-other-opencode.db"
            empty_db(db)
            message = self._no_session(["--cwd", CWD, "--db", str(db)])
        self.assertIn(str(db), message)
        self.assertNotIn(str(self.mod.default_db_path()), message)
        self.assertIn(CWD, message)

    def test_no_session_names_db_flag_over_opencode_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected = Path(tmp) / "selected.db"
            other = Path(tmp) / "env-only.db"
            empty_db(selected)
            empty_db(other)
            os.environ["OPENCODE_DB"] = str(other)
            message = self._no_session(
                ["--cwd", CWD, "--db", str(selected)]
            )
        self.assertIn(str(selected), message)
        self.assertNotIn(str(other), message)

    def test_no_session_names_opencode_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "env-opencode.db"
            empty_db(db)
            os.environ["OPENCODE_DB"] = str(db)
            message = self._no_session(["--cwd", CWD])
        self.assertIn(str(db), message)

    def test_no_session_names_default_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["HOME"] = tmp
            db = Path(tmp) / ".local" / "share" / "opencode" / "opencode.db"
            db.parent.mkdir(parents=True)
            empty_db(db)
            message = self._no_session(["--cwd", CWD])
        self.assertIn(str(db), message)

    def test_missing_database_names_attempted_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.db"
            message = self._no_session(["--cwd", CWD, "--db", str(missing)])
        self.assertIn(str(missing), message)
        self.assertIn("No OpenCode database", message)

    def test_matching_session_extracts_from_selected_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected = Path(tmp) / "selected.db"
            other = Path(tmp) / "env-only.db"
            empty_db(other)
            session_db(selected, CWD, "ses_probe", "ship the fix")
            os.environ["OPENCODE_DB"] = str(other)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = self.mod.main(
                    ["--cwd", CWD, "--db", str(selected)]
                )
        text = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("session_id: ses_probe", text)
        self.assertIn(f"db: {selected}", text)
        self.assertIn("ship the fix", text)
        self.assertNotIn(str(other), text)
