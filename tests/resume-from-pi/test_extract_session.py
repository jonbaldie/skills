#!/usr/bin/env python3
"""Unit tests for resume-from-pi extract-session.py (temp HOME only)."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "resume-from-pi" / "scripts" / "extract-session.py"

CWD = "/Users/x/proj"
SID = "aaaaaaaa-bbbb-cccc"
DECOY = SID + "zz"


def load_mod():
    spec = importlib.util.spec_from_file_location("extract_session_rfp", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_session_rfp"] = mod
    spec.loader.exec_module(mod)
    return mod


def write_jsonl(path: Path, session_id: str, prompt: str) -> None:
    path.write_text(
        json.dumps({"type": "session", "id": session_id, "cwd": CWD})
        + "\n"
        + json.dumps(
            {
                "type": "message",
                "message": {"role": "user", "content": prompt},
            }
        )
        + "\n"
    )


class ResolveSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def _home(self, tmp: str) -> Path:
        home = Path(tmp)
        old = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        self.addCleanup(self._restore_home, old)
        return home

    def _restore_home(self, old: str | None) -> None:
        if old is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old

    def _sess_dir(self, home: Path) -> Path:
        path = home / ".pi" / "agent" / "sessions" / self.mod.encode_cwd(CWD)
        path.mkdir(parents=True)
        return path

    def test_exact_suffix_beats_newer_prefix_decoy(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            sess = self._sess_dir(home)
            exact = sess / f"20260101T120000_{SID}.jsonl"
            decoy = sess / f"20260101T130000_{DECOY}.jsonl"
            write_jsonl(exact, SID, "exact prompt")
            write_jsonl(decoy, DECOY, "decoy prompt")
            os.utime(exact, (1_700_000_000, 1_700_000_000))
            os.utime(decoy, (1_700_003_600, 1_700_003_600))

            chosen = self.mod.resolve_session(CWD, SID)
            self.assertEqual(chosen, exact)

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = self.mod.main(["--cwd", CWD, SID])
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn(f"session_id: {SID}", out)
            self.assertNotIn(f"session_id: {DECOY}", out)
            self.assertIn("exact prompt", out)
            self.assertNotIn("decoy prompt", out)

    def test_stem_equal_to_id_is_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            sess = self._sess_dir(home)
            exact = sess / f"{SID}.jsonl"
            decoy = sess / f"20260101T130000_{DECOY}.jsonl"
            write_jsonl(exact, SID, "stem prompt")
            write_jsonl(decoy, DECOY, "decoy prompt")
            os.utime(exact, (1_700_000_000, 1_700_000_000))
            os.utime(decoy, (1_700_003_600, 1_700_003_600))

            chosen = self.mod.resolve_session(CWD, SID)
            self.assertEqual(chosen, exact)

    def test_partial_id_without_exact_suffix_uses_substring(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            sess = self._sess_dir(home)
            older = sess / f"20260101T120000_{SID}.jsonl"
            newer = sess / f"20260101T130000_{DECOY}.jsonl"
            write_jsonl(older, SID, "older")
            write_jsonl(newer, DECOY, "newer")
            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_700_003_600, 1_700_003_600))

            chosen = self.mod.resolve_session(CWD, "aaaaaaaa-bbbb")
            self.assertEqual(chosen, newer)

    def test_single_glob_hit_returned_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            sess = self._sess_dir(home)
            only = sess / f"20260101T120000_{SID}.jsonl"
            write_jsonl(only, SID, "only prompt")
            decoy = sess / "20260101T130000_zzzzzzzz-yyyy-xxxx.jsonl"
            write_jsonl(decoy, "zzzzzzzz-yyyy-xxxx", "other")
            os.utime(only, (1_700_000_000, 1_700_000_000))
            os.utime(decoy, (1_700_003_600, 1_700_003_600))

            chosen = self.mod.resolve_session(CWD, SID)
            self.assertEqual(chosen, only)


if __name__ == "__main__":
    unittest.main()
