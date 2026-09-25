#!/usr/bin/env python3
"""Tests for resume-from-codex extract-session.py."""

from __future__ import annotations

import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
