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

    def _cwd_pair(self, home: Path) -> tuple[Path, Path]:
        physical_cwd = home / "workspace" / "project"
        physical_cwd.mkdir(parents=True)
        symlink_cwd = home / "workspace" / "project-link"
        symlink_cwd.symlink_to(physical_cwd, target_is_directory=True)
        return physical_cwd, symlink_cwd

    def _project_session_dir(self, home: Path, cwd: Path) -> Path:
        return home / ".pi" / "agent" / "sessions" / self.mod.encode_cwd(str(cwd))

    def _write_project_session(
        self, session_dir: Path, session_id: str, prompt: str, cwd: Path
    ) -> Path:
        session_dir.mkdir(parents=True, exist_ok=True)
        session = session_dir / f"20260101T120000_{session_id}.jsonl"
        session.write_text(
            json.dumps({"type": "session", "id": session_id, "cwd": str(cwd)})
            + "\n"
            + json.dumps(
                {
                    "type": "message",
                    "message": {"role": "user", "content": prompt},
                }
            )
            + "\n"
        )
        return session

    def test_symlinked_cwd_finds_session_under_physical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, symlink_cwd = self._cwd_pair(home)
            self._write_project_session(
                self._project_session_dir(home, physical_cwd.resolve()),
                "pi-physical-session",
                "pi physical prompt",
                physical_cwd.resolve(),
            )

            output = io.StringIO()
            with redirect_stdout(output):
                self.mod.main(["--cwd", str(symlink_cwd)])

            self.assertIn("session_id: pi-physical-session", output.getvalue())
            self.assertIn("pi physical prompt", output.getvalue())

    def test_physical_cwd_still_finds_its_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, _ = self._cwd_pair(home)
            self._write_project_session(
                self._project_session_dir(home, physical_cwd),
                "pi-direct-session",
                "pi direct prompt",
                physical_cwd,
            )

            output = io.StringIO()
            with redirect_stdout(output):
                code = self.mod.main(["--cwd", str(physical_cwd)])

            self.assertEqual(code, 0)
            self.assertIn("session_id: pi-direct-session", output.getvalue())
            self.assertIn("pi direct prompt", output.getvalue())

    def test_both_cwd_keys_choose_the_newest_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, symlink_cwd = self._cwd_pair(home)
            logical_session = self._write_project_session(
                self._project_session_dir(home, symlink_cwd),
                "pi-logical-session",
                "older logical prompt",
                symlink_cwd,
            )
            physical_session = self._write_project_session(
                self._project_session_dir(home, physical_cwd.resolve()),
                "pi-physical-session",
                "newer physical prompt",
                physical_cwd.resolve(),
            )
            os.utime(logical_session, (1_700_000_000, 1_700_000_000))
            os.utime(physical_session, (1_700_003_600, 1_700_003_600))

            output = io.StringIO()
            with redirect_stdout(output):
                self.mod.main(["--cwd", str(symlink_cwd)])

            self.assertIn("session_id: pi-physical-session", output.getvalue())
            self.assertIn("newer physical prompt", output.getvalue())
            self.assertNotIn("pi-logical-session", output.getvalue())

    def test_explicit_jsonl_lookup_remains_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            physical_cwd, symlink_cwd = self._cwd_pair(home)
            manual_session = home / "manual-session.jsonl"
            manual_session.write_text(
                json.dumps(
                    {
                        "type": "session",
                        "id": "pi-jsonl-session",
                        "cwd": str(physical_cwd),
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "message",
                        "message": {
                            "role": "user",
                            "content": "pi explicit jsonl prompt",
                        },
                    }
                )
                + "\n"
            )

            output = io.StringIO()
            with redirect_stdout(output):
                code = self.mod.main(
                    ["--cwd", str(symlink_cwd), "--jsonl", str(manual_session)]
                )

            self.assertEqual(code, 0)
            self.assertIn("pi explicit jsonl prompt", output.getvalue())
            self.assertIn(str(manual_session), output.getvalue())

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
