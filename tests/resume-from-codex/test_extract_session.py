#!/usr/bin/env python3
"""Tests for resume-from-codex extract-session.py."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "resume-from-codex" / "scripts" / "extract-session.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("extract_session_rfcx", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_session_rfcx"] = mod
    spec.loader.exec_module(mod)
    return mod


def record(kind: str, payload: dict) -> dict:
    return {"timestamp": "2026-01-01T00:00:00Z", "type": kind, "payload": payload}


SESSION_META = record("session_meta", {"id": "rollout-xyz", "cwd": "/ws"})
ASSISTANT_ITEM = record(
    "response_item",
    {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "All shipped."}],
    },
)


def user_item(text: str) -> dict:
    return record(
        "response_item",
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    )


def user_event(text: str) -> dict:
    return record("event_msg", {"type": "user_message", "message": text})


class ParseSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def brief(self, records: list[dict]) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in records))
            return self.mod.render(self.mod.parse_session(path))

    def test_response_item_user_prompt_becomes_goal_and_last_prompt(self):
        out = self.brief([SESSION_META, user_item("Ship the PR"), ASSISTANT_ITEM])

        self.assertIn("last_prompt: Ship the PR", out)
        self.assertIn("## Opening goal\n\n### User\nShip the PR", out)

    def test_response_item_user_prompt_contributes_skills(self):
        out = self.brief(
            [SESSION_META, user_item("[$ship-pr](/s/SKILL.md) go"), ASSISTANT_ITEM]
        )

        self.assertIn("## Skills invoked\n- ship-pr", out)

    def test_event_msg_prompt_is_not_duplicated_by_its_response_item(self):
        out = self.brief(
            [
                SESSION_META,
                user_item("<environment_context>cwd</environment_context>"),
                user_item("Ship the PR"),
                user_event("Ship the PR"),
                ASSISTANT_ITEM,
            ]
        )

        self.assertEqual(out.count("Ship the PR"), 3)  # last_prompt, goal, recent

    def test_injected_context_items_are_not_user_turns(self):
        out = self.brief(
            [
                SESSION_META,
                user_item("<user_instructions>AGENTS rules</user_instructions>"),
                user_item("<environment_context>cwd</environment_context>"),
                user_item("Ship the PR"),
                ASSISTANT_ITEM,
            ]
        )

        self.assertNotIn("AGENTS rules", out)
        self.assertEqual(out.count("### User"), 2)  # goal + recent

    def test_injected_agents_md_instructions_are_not_user_turns(self):
        out = self.brief(
            [
                SESSION_META,
                user_item(
                    "# AGENTS.md instructions for /ws\n\n<INSTRUCTIONS>\n"
                    "Repo rules\n</INSTRUCTIONS>"
                ),
                user_item("Ship the PR"),
                ASSISTANT_ITEM,
            ]
        )

        self.assertNotIn("Repo rules", out)
        self.assertEqual(out.count("### User"), 2)  # goal + recent

    def test_injected_skill_body_counts_as_skill_not_prompt(self):
        out = self.brief(
            [
                SESSION_META,
                user_item("use $ship-pr to ship"),
                user_item("<skill>\n<name>ship-pr</name>\nSkill body\n</skill>"),
                ASSISTANT_ITEM,
            ]
        )

        self.assertIn("last_prompt: use $ship-pr to ship", out)
        self.assertIn("## Skills invoked\n- ship-pr", out)
        self.assertEqual(out.count("### User"), 2)  # goal + recent

    def test_response_item_user_prompt_xml_skill_tag(self):
        out = self.brief(
            [
                SESSION_META,
                user_item(
                    "<skill>\n<name>implement-spec</name>\n</skill>\nbuild the feature"
                ),
                ASSISTANT_ITEM,
            ]
        )

        self.assertIn("last_prompt: [skill] implement-spec\nbuild the feature", out)
        self.assertIn("## Skills invoked\n- implement-spec", out)

    def test_event_msg_user_message_still_works(self):
        out = self.brief(
            [
                SESSION_META,
                user_event("Legacy user prompt"),
                record(
                    "event_msg",
                    {"type": "agent_message", "message": "Legacy assistant reply"},
                ),
            ]
        )

        self.assertIn("last_prompt: Legacy user prompt", out)
        self.assertIn("Legacy assistant reply", out)


class CustomCodexHomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_sessions_root_and_index_path_honor_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom_dir = Path(tmp) / "custom_codex"
            old_codex_home = os.environ.get("CODEX_HOME")
            try:
                os.environ["CODEX_HOME"] = str(custom_dir)
                self.assertEqual(self.mod.sessions_root(), custom_dir / "sessions")
                self.assertEqual(
                    self.mod.session_index_path(),
                    custom_dir / "session_index.jsonl",
                )
            finally:
                if old_codex_home is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = old_codex_home

    def test_resolve_session_with_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom_dir = Path(tmp) / "custom_codex"
            sessions_dir = custom_dir / "sessions" / "2026" / "01" / "01"
            sessions_dir.mkdir(parents=True)
            rollout = sessions_dir / "rollout-2026-01-01T00-00-00-custom-id.jsonl"
            rollout.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"id": "custom-id", "cwd": "/ws"},
                    }
                )
                + "\n"
            )
            index_path = custom_dir / "session_index.jsonl"
            index_path.write_text(
                json.dumps({"id": "custom-id", "thread_name": "Custom Feature"})
                + "\n"
            )

            old_codex_home = os.environ.get("CODEX_HOME")
            try:
                os.environ["CODEX_HOME"] = str(custom_dir)
                resolved = self.mod.resolve_session("/ws", None)
                self.assertEqual(resolved, rollout)

                resolved_by_thread = self.mod.resolve_session(
                    "/ws", "Custom Feature"
                )
                self.assertEqual(resolved_by_thread, rollout)
            finally:
                if old_codex_home is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = old_codex_home

    def test_codex_home_unset_or_empty_falls_back_to_home(self):
        old_codex_home = os.environ.get("CODEX_HOME")
        try:
            os.environ.pop("CODEX_HOME", None)
            self.assertEqual(
                self.mod.sessions_root(), Path.home() / ".codex" / "sessions"
            )
            self.assertEqual(
                self.mod.session_index_path(),
                Path.home() / ".codex" / "session_index.jsonl",
            )

            os.environ["CODEX_HOME"] = ""
            self.assertEqual(
                self.mod.sessions_root(), Path.home() / ".codex" / "sessions"
            )
            self.assertEqual(
                self.mod.session_index_path(),
                Path.home() / ".codex" / "session_index.jsonl",
            )
        finally:
            if old_codex_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old_codex_home


if __name__ == "__main__":
    unittest.main()
