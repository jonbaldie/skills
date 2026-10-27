#!/usr/bin/env python3
"""Unit tests for resume-from-pi extract-session.py (temp HOME only)."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import isolated_env, load_skill_script, make_workspace_symlink_pair, run_cli

CWD = "/Users/x/proj"
SID = "aaaaaaaa-bbbb-cccc"
DECOY = SID + "zz"


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
        cls.mod = load_skill_script("resume-from-pi", "extract-session.py")

    def _home(self, tmp: str) -> Path:
        home = Path(tmp)
        self.enterContext(isolated_env(HOME=str(home)))
        return home

    def _sess_dir(self, home: Path) -> Path:
        path = home / ".pi" / "agent" / "sessions" / self.mod.encode_cwd(CWD)
        path.mkdir(parents=True)
        return path

    _cwd_pair = staticmethod(make_workspace_symlink_pair)

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

            output = run_cli(self.mod.main, ["--cwd", str(symlink_cwd)])

            self.assertIn("session_id: pi-physical-session", output)
            self.assertIn("pi physical prompt", output)

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

    def _colliding_cwds(self, home: Path) -> tuple[Path, Path, Path]:
        """Two real workspaces whose cwd encodes to one Pi directory (#215)."""
        mine = home / "apps" / "web-api"
        other = home / "apps-web" / "api"
        mine.mkdir(parents=True)
        other.mkdir(parents=True)
        session_dir = self._project_session_dir(home, mine)
        self.assertEqual(session_dir, self._project_session_dir(home, other))
        return mine, other, session_dir

    def test_colliding_cwd_ignores_newer_other_project_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            mine, other, session_dir = self._colliding_cwds(home)
            own = self._write_project_session(
                session_dir, "pi-own-session", "own project goal", mine
            )
            foreign = session_dir / "20260101T130000_pi-other-session.jsonl"
            foreign.write_text(
                json.dumps(
                    {"type": "session", "id": "pi-other-session", "cwd": str(other)}
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "message",
                        "message": {"role": "user", "content": "other project goal"},
                    }
                )
                + "\n"
            )
            os.utime(own, (1_700_000_000, 1_700_000_000))
            os.utime(foreign, (1_700_003_600, 1_700_003_600))

            output = io.StringIO()
            with redirect_stdout(output):
                code = self.mod.main(["--cwd", str(mine)])

            self.assertEqual(code, 0)
            self.assertIn("session_id: pi-own-session\n", output.getvalue())
            self.assertIn(f"cwd: {mine}\n", output.getvalue())
            self.assertIn("own project goal", output.getvalue())
            self.assertNotIn("other project goal", output.getvalue())

            # Only the unrelated session left: no-id discovery must not emit it.
            own.unlink()
            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                self.mod.main(["--cwd", str(mine)])
            self.assertIn(str(other), str(raised.exception))
            self.assertNotIn("other project goal", output.getvalue())

            # Pinning the other project's id stays available and truthful.
            output = io.StringIO()
            with redirect_stdout(output):
                code = self.mod.main(["--cwd", str(mine), "pi-other-session"])
            self.assertEqual(code, 0)
            self.assertIn("session_id: pi-other-session\n", output.getvalue())
            self.assertIn(f"cwd: {other}\n", output.getvalue())
            self.assertIn("other project goal", output.getvalue())

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
