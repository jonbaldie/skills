"""Exercise tool text through independently installed extractor CLIs."""

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("resume-from-codex", "resume-from-opencode", "resume-from-agent")
BLOB = ('*** Update File: src/a file.py\n*** Add File: src/a file.py\n'
        '"path": "src/a file.py"\n"filePath": "src/other file.py"\n'
        '"file_path": "bad\\tpath"\n"path": "{}"\n"path": ""\n'
        '*** Delete File: ' + 'x' * 513 + '\n')


class ToolTextPathsTests(unittest.TestCase):
    def test_bundled_parsers_remain_identical(self):
        copies = [(ROOT / "skills" / skill / "scripts/tool_text_paths.py").read_bytes()
                  for skill in SKILLS]
        self.assertEqual(copies[0], copies[1])
        self.assertEqual(copies[0], copies[2])

    def test_parser_validates_and_preserves_occurrences(self):
        path = ROOT / "skills/resume-from-codex/scripts/tool_text_paths.py"
        spec = importlib.util.spec_from_file_location("tool_text_paths_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        text = (BLOB + '"path": "   "\n"path": "line\\nfeed"\n'
                '"file_path": "dir/quote\\"name.py"\n'
                '*** Delete File: spaced name.py\\n@@ patch')
        self.assertEqual(module.paths_from_tool_text(text), [
            "src/a file.py", "src/a file.py", "src/a file.py", "src/other file.py",
            'dir/quote"name.py', "spaced name.py",
        ])

    def test_independent_installs_extract_same_paths(self):
        with tempfile.TemporaryDirectory(prefix="path test ") as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
            env.pop("CODEX_HOME", None)
            for skill in SKILLS:
                project = root / skill
                project.mkdir()
                install = subprocess.run(
                    [str(ROOT / "install.sh"), "--agent", "pi", "--without-prereqs",
                     "--copy", "--skill", skill], cwd=project, env=env,
                    capture_output=True, text=True)
                self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
                script = project / ".pi/skills" / skill / "scripts/extract-session.py"
                if skill == "resume-from-codex":
                    transcript = root / "rollout with spaces.jsonl"
                    rows = [{"type": "session_meta", "payload": {"id": "test", "cwd": str(project)}},
                            {"type": "response_item", "payload": {"type": "custom_tool_call",
                             "name": "apply_patch", "input": BLOB}}]
                    transcript.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                    args = ["--jsonl", str(transcript)]
                elif skill == "resume-from-opencode":
                    db = root / "open code.db"
                    conn = sqlite3.connect(db)
                    conn.executescript('''
                        CREATE TABLE session (id TEXT, directory TEXT, path TEXT, time_archived INTEGER,
                          time_updated INTEGER, project_id TEXT, slug TEXT, title TEXT, agent TEXT,
                          model TEXT, version TEXT, time_created INTEGER);
                        CREATE TABLE project (id TEXT, worktree TEXT);
                        CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
                        CREATE TABLE part (id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
                        CREATE TABLE todo (content TEXT, status TEXT, priority TEXT, position INTEGER, session_id TEXT);
                        CREATE TABLE session_message (type TEXT, data TEXT, time_created INTEGER, session_id TEXT, seq INTEGER);
                        INSERT INTO session (id, directory, time_updated, time_created) VALUES ('test', 'cwd', 1, 1);
                        INSERT INTO message VALUES ('m', 'test', 1, '{"role":"assistant"}');
                    ''')
                    conn.execute("INSERT INTO part VALUES ('p', 'm', 'test', 1, ?)",
                                 (json.dumps({"type": "tool", "tool": "apply_patch", "state":
                                              {"status": "completed", "input": {"patchText": BLOB}}}),))
                    conn.commit()
                    conn.close()
                    args = ["--db", str(db), "test"]
                else:
                    db = home / ".hermes/state.db"
                    db.parent.mkdir()
                    conn = sqlite3.connect(db)
                    conn.executescript('''
                        CREATE TABLE sessions (id TEXT, title TEXT, cwd TEXT, model TEXT, started_at REAL,
                          ended_at REAL, message_count INTEGER, git_branch TEXT, end_reason TEXT, source TEXT, active INTEGER);
                        CREATE TABLE messages (id INTEGER, session_id TEXT, role TEXT, content TEXT,
                          tool_calls TEXT, tool_name TEXT, timestamp REAL, finish_reason TEXT, active INTEGER);
                    ''')
                    conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 ("test", "title", str(project), "model", 1, 2, 1, "main", None, "cli", 1))
                    calls = json.dumps([{"function": {"name": "apply_patch", "arguments": BLOB}}])
                    conn.execute("INSERT INTO messages VALUES (1, 'test', 'assistant', '', ?, NULL, 1, NULL, 1)", (calls,))
                    conn.commit()
                    conn.close()
                    args = ["--cwd", str(project), "--agent", "hermes"]
                result = subprocess.run([sys.executable, str(script), *args], cwd=project, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('- src/a file.py (3)', result.stdout)
                self.assertIn('- src/other file.py (1)', result.stdout)
                self.assertNotIn('bad\tpath', result.stdout)
                self.assertNotIn('- {} (', result.stdout)
                self.assertNotIn('x' * 513, result.stdout)


if __name__ == "__main__":
    unittest.main()
