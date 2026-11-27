"""Standalone extractors ignore JSONL values that are not records."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("agent", ["claude", "pi", "codex"])
@pytest.mark.parametrize("invalid", ["null", "[]", "0", '"x"', "true"])
def test_cli_skips_non_object_lines(tmp_path, agent, invalid):
    path = tmp_path / "session.jsonl"
    script = ROOT / "skills" / f"resume-from-{agent}" / "scripts" / "extract-session.py"
    record = '{"type":"user","message":{"content":"hello"}}\n'

    def run(prefix):
        path.write_text(prefix + "\n" + record)
        os.utime(path, (1_700_000_000, 1_700_000_000))
        return subprocess.run([sys.executable, str(script), "--jsonl", str(path)],
                              capture_output=True, text=True)

    control = run("not json")
    actual = run(invalid)
    assert control.returncode == 0
    assert actual.returncode == 0, actual.stderr
    assert actual.stdout == control.stdout


def test_claude_skips_unhashable_type(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_text('{"type":[]}\n{"type":"user","message":{"content":"hello"}}\n')
    script = ROOT / "skills/resume-from-claude/scripts/extract-session.py"
    result = subprocess.run([sys.executable, str(script), "--jsonl", str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "hello" in result.stdout


def test_codex_index_skips_non_objects(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "tests"))
    from harness import load_skill_script

    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "session_index.jsonl").write_text('null\n[]\n{"id":"abc","thread_name":"Example"}\n')
    mod = load_skill_script("resume-from-codex", "extract-session.py")
    assert mod.load_thread_names() == {"abc": "Example"}
