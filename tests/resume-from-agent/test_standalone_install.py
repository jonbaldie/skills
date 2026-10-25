"""Regression coverage through a real selectively installed router CLI."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class StandaloneInstallTests(unittest.TestCase):
    def test_codex_discovery_preserves_rollout_without_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            project = Path(tmp) / "project"
            home.mkdir()
            project.mkdir()
            env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
            for key in ("CODEX_HOME", "CLAUDE_CONFIG_DIR"):
                env.pop(key, None)

            def run(*args):
                result = subprocess.run(
                    [str(arg) for arg in args], cwd=project, env=env,
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            def install(skill):
                run(ROOT / "install.sh", "--agent", "pi", "--without-prereqs",
                    "--skill", skill)

            install("resume-from-agent")
            skills = project / ".agents" / "skills"
            self.assertFalse((skills / "resume-from-codex").exists())
            router = skills / "resume-from-agent" / "scripts" / "extract-session.py"
            sid = "11111111-1111-4111-8111-111111111111"
            rollout = home / ".codex" / "sessions" / "2026" / "10" / "24" / (
                f"rollout-2026-10-24T00-00-00-{sid}.jsonl"
            )
            rollout.parent.mkdir(parents=True)
            goal = "Implement invoice rounding and add boundary tests."
            reply = "I will add rounding tests next."
            rows = [
                {"type": "session_meta", "payload": {"id": sid, "cwd": str(project)}},
                {"type": "event_msg", "payload": {"type": "user_message", "message": goal}},
                {"type": "response_item", "payload": {"type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": goal}]}},
                {"type": "event_msg", "payload": {"type": "agent_message", "message": reply}},
                {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": reply}]}},
                {"type": "event_msg", "payload": {"type": "turn_aborted", "reason": "interrupted"}},
            ]
            rollout.write_text("".join(json.dumps(row) + "\n" for row in rows))

            def assert_brief(text):
                self.assertIn(goal, text)
                self.assertIn(reply, text)
                self.assertIn("turn_aborted: interrupted", text)
                self.assertIn(f"session_id: {sid}\n", text)
                self.assertIn(f"cwd: {project}\n", text)
                self.assertIn(str(rollout), text)
                recent = text.split("## Recent turns\n", 1)[1].split("## Ending\n", 1)[0]
                self.assertEqual(recent.count("### User\n"), 1)
                self.assertEqual(recent.count("### Assistant\n"), 1)

            # Controls and discovery use the exact same installed CLI and rollout.
            assert_brief(run(sys.executable, router, "--agent", "codex", "--path", rollout))
            discovered = run(sys.executable, router, "--cwd", project, "codex")
            install("resume-from-codex")
            assert_brief(run(sys.executable, router, "--cwd", project, "codex"))
            assert_brief(discovered)


if __name__ == "__main__":
    unittest.main()
