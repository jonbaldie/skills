"""Real-file contract tests for the independently installed SQLite extractors."""

import importlib.util
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing


ROOT = Path(__file__).resolve().parents[1]
OPENERS = (
    ("resume-from-agent", "open_sqlite_ro", FileNotFoundError),
    ("resume-from-opencode", "connect", SystemExit),
)
NAMES = ("plain", "percent%41", "question?", "hash#", "a space", "café")


class SQLiteOpenerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def load_opener(self, skill, name):
        # Import a standalone installed copy, with no sibling scripts or helpers.
        installed = self.root / skill / "scripts" / "extract-session.py"
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "skills" / skill / "scripts" / installed.name, installed)
        module_name = "sqlite_contract_" + skill.replace("-", "_")
        spec = importlib.util.spec_from_file_location(module_name, installed)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        self.addCleanup(sys.modules.pop, module_name, None)
        spec.loader.exec_module(mod)
        return getattr(mod, name)

    def test_literal_paths_read_only_without_filesystem_changes(self):
        for skill, name, _ in OPENERS:
            opener = self.load_opener(skill, name)
            for component in NAMES:
                # Exercise metacharacters in parent directories and filenames.
                parent = self.root / skill / component
                parent.mkdir()
                db = parent / (component + ".db")
                with closing(sqlite3.connect(db)) as conn:
                    conn.execute("CREATE TABLE marker(value TEXT)")
                    conn.execute("INSERT INTO marker VALUES (?)", (str(db),))
                    conn.commit()
                original = db.read_bytes()
                before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
                for path in (db, Path(os.path.relpath(db))):
                    with self.subTest(skill=skill, path=str(path)):
                        with closing(opener(path)) as conn:
                            self.assertEqual(conn.execute("SELECT value FROM marker").fetchone()["value"], str(db))
                            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 15000)
                            self.assertEqual(conn.execute("PRAGMA query_only").fetchone()[0], 1)
                            # Prove the open itself is read-only, not just query_only.
                            conn.execute("PRAGMA query_only = OFF")
                            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                                conn.execute("UPDATE marker SET value = 'changed'")
                        self.assertEqual(db.read_bytes(), original)
                        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob("*")), before)

    def test_missing_paths_keep_adapter_errors_and_create_nothing(self):
        for skill, name, error in OPENERS:
            opener = self.load_opener(skill, name)
            for component in NAMES:
                missing = self.root / skill / (component + ".db")
                for path in (missing, Path(os.path.relpath(missing))):
                    with self.subTest(skill=skill, path=str(path)):
                        before = sorted(self.root.rglob("*"))
                        with self.assertRaises(error) as caught:
                            opener(path)
                        expected = str(path) if error is FileNotFoundError else f"No OpenCode database at {path}"
                        self.assertEqual(str(caught.exception), expected)
                        self.assertEqual(sorted(self.root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
