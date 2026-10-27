import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import isolated_env, load_skill_script, make_workspace_symlink_pair, run_cli


class HarnessTests(unittest.TestCase):
    def test_environment_restored_after_success_and_exception(self):
        with patch.dict(os.environ, {"PSTACK_PRESENT": "before"}):
            os.environ.pop("PSTACK_ABSENT", None)
            with isolated_env(PSTACK_PRESENT="inside", PSTACK_ABSENT="new"):
                self.assertEqual(os.environ["PSTACK_PRESENT"], "inside")
                self.assertEqual(os.environ["PSTACK_ABSENT"], "new")
            self.assertEqual(os.environ["PSTACK_PRESENT"], "before")
            self.assertNotIn("PSTACK_ABSENT", os.environ)
            with self.assertRaisesRegex(ValueError, "stop"):
                with isolated_env(PSTACK_PRESENT=None, PSTACK_ABSENT="new"):
                    self.assertNotIn("PSTACK_PRESENT", os.environ)
                    raise ValueError("stop")
            self.assertEqual(os.environ["PSTACK_PRESENT"], "before")
            self.assertNotIn("PSTACK_ABSENT", os.environ)

    def test_distinct_scripts_and_real_entry_point(self):
        pi = load_skill_script("resume-from-pi", "extract-session.py")
        claude = load_skill_script("resume-from-claude", "extract-session.py")
        self.assertNotEqual(pi.__name__, claude.__name__)
        self.assertNotEqual(pi.__file__, claude.__file__)
        with tempfile.TemporaryDirectory() as tmp, isolated_env(HOME=tmp):
            physical, link = make_workspace_symlink_pair(Path(tmp))
            (physical / "example").write_text("content")
            self.assertEqual((link / "example").read_text(), "content")
            with self.assertRaises(SystemExit) as raised:
                run_cli(pi.main, ["--help"])
            self.assertEqual(raised.exception.code, 0)
            session_dir = physical / "sessions"
            session_dir.mkdir()
            session = session_dir / "test.jsonl"
            session.write_text('{"type":"session","id":"sample","cwd":"/tmp"}\n'
                               '{"type":"message","message":{"role":"user","content":"hello"}}\n')
            output = run_cli(pi.main, ["--jsonl", str(session)])
            self.assertIn("sample", output)
            self.assertIn("hello", output)
