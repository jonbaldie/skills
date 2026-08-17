#!/usr/bin/env python3
"""Unit tests for resume-from-pr extract-pr.py (no live network)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "resume-from-pr" / "scripts" / "extract-pr.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("extract_pr", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extract_pr"] = mod
    spec.loader.exec_module(mod)
    return mod


class ParseUrlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def parse(self, url: str):
        return self.mod.parse_pr_url(url)

    def test_github_pull(self):
        t = self.parse("https://github.com/owner/repo/pull/42")
        self.assertEqual(t.provider, "github")
        self.assertEqual(t.host, "github.com")
        self.assertEqual(t.owner, "owner")
        self.assertEqual(t.repo, "repo")
        self.assertEqual(t.number, "42")
        self.assertEqual(t.slug, "owner/repo")

    def test_github_strips_tab_and_patch(self):
        t = self.parse("https://github.com/owner/repo/pull/42/files")
        self.assertEqual(t.number, "42")
        t = self.parse("https://github.com/owner/repo/pull/42.diff")
        self.assertEqual(t.url, "https://github.com/owner/repo/pull/42")

    def test_github_enterprise(self):
        t = self.parse("https://ghe.example.com/acme/app/pull/9")
        self.assertEqual(t.provider, "github")
        self.assertEqual(t.host, "ghe.example.com")
        self.assertEqual(t.number, "9")

    def test_gitlab_nested_group(self):
        t = self.parse(
            "https://gitlab.com/group/sub/project/-/merge_requests/7"
        )
        self.assertEqual(t.provider, "gitlab")
        self.assertEqual(t.project, "group/sub/project")
        self.assertEqual(t.owner, "group/sub")
        self.assertEqual(t.repo, "project")
        self.assertEqual(t.number, "7")

    def test_gitlab_legacy_path(self):
        t = self.parse("https://gitlab.example.com/team/app/merge_requests/3")
        self.assertEqual(t.provider, "gitlab")
        self.assertEqual(t.host, "gitlab.example.com")
        self.assertEqual(t.number, "3")

    def test_bitbucket_cloud(self):
        t = self.parse(
            "https://bitbucket.org/workspace/repo/pull-requests/11/diff"
        )
        self.assertEqual(t.provider, "bitbucket")
        self.assertEqual(t.owner, "workspace")
        self.assertEqual(t.repo, "repo")
        self.assertEqual(t.number, "11")

    def test_bitbucket_server(self):
        t = self.parse(
            "https://bitbucket.example.com/projects/KEY/repos/slug/pull-requests/4"
        )
        self.assertEqual(t.provider, "bitbucket-server")
        self.assertEqual(t.owner, "KEY")
        self.assertEqual(t.repo, "slug")
        self.assertEqual(t.number, "4")

    def test_gitea_and_codeberg(self):
        t = self.parse("https://codeberg.org/owner/repo/pulls/9")
        self.assertEqual(t.provider, "gitea")
        self.assertEqual(t.host, "codeberg.org")
        self.assertEqual(t.number, "9")

    def test_azure_devops(self):
        t = self.parse(
            "https://dev.azure.com/org/project/_git/repo/pullrequest/15"
        )
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.org, "org")
        self.assertEqual(t.project, "project")
        self.assertEqual(t.repo, "repo")
        self.assertEqual(t.number, "15")

    def test_azure_visualstudio(self):
        t = self.parse(
            "https://contoso.visualstudio.com/proj/_git/repo/pullrequest/2"
        )
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.org, "contoso")
        self.assertEqual(t.project, "proj")
        self.assertEqual(t.number, "2")

    def test_markdown_link_and_angle_brackets(self):
        t = self.mod.parse_argument(
            "[PR](https://github.com/owner/repo/pull/1)"
        )
        self.assertEqual(t.number, "1")
        t = self.mod.parse_argument("<https://github.com/owner/repo/pull/2>")
        self.assertEqual(t.number, "2")

    def test_embedded_url_in_sentence(self):
        t = self.mod.parse_argument(
            "please continue https://github.com/owner/repo/pull/8 thanks"
        )
        self.assertEqual(t.number, "8")

    def test_scheme_optional(self):
        t = self.parse("github.com/owner/repo/pull/3")
        self.assertEqual(t.provider, "github")
        self.assertEqual(t.number, "3")

    def test_shorthand_github_and_gitlab(self):
        t = self.mod.parse_argument("owner/repo#12")
        self.assertEqual(t.provider, "github")
        self.assertEqual(t.number, "12")
        t = self.mod.parse_argument("group/project!4")
        self.assertEqual(t.provider, "gitlab")
        self.assertEqual(t.number, "4")
        self.assertEqual(t.project, "group/project")

    def test_bare_number(self):
        t = self.mod.parse_argument("42")
        self.assertEqual(t.provider, "unknown")
        self.assertEqual(t.number, "42")
        t = self.mod.parse_argument("!7")
        self.assertEqual(t.number, "7")

    def test_unknown_url_errors(self):
        with self.assertRaises(self.mod.FetchError):
            self.parse("https://example.com/not-a-pr")


class RemoteAndApiRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_parse_git_remote_https_and_ssh(self):
        host, path = self.mod.parse_git_remote(
            "https://github.com/owner/repo.git"
        )
        self.assertEqual(host, "github.com")
        self.assertEqual(path, "owner/repo")
        host, path = self.mod.parse_git_remote("git@gitlab.com:group/app.git")
        self.assertEqual(host, "gitlab.com")
        self.assertEqual(path, "group/app")

    def test_target_from_remote(self):
        t = self.mod.target_from_remote(
            "5", "https://github.com/acme/app.git"
        )
        self.assertEqual(t.provider, "github")
        self.assertEqual(t.url, "https://github.com/acme/app/pull/5")
        t = self.mod.target_from_remote(
            "2", "git@codeberg.org:owner/repo.git"
        )
        self.assertEqual(t.provider, "gitea")
        self.assertTrue(t.url.endswith("/pulls/2"))

    def test_github_api_root(self):
        self.assertEqual(
            self.mod.github_api_root("github.com"), "https://api.github.com"
        )
        self.assertEqual(
            self.mod.github_api_root("ghe.example.com"),
            "https://ghe.example.com/api/v3",
        )

    def test_gitlab_project_id_encodes_slash(self):
        target = self.mod.Target(
            provider="gitlab",
            host="gitlab.com",
            number="1",
            project="group/sub/app",
        )
        self.assertEqual(self.mod.gitlab_project_id(target), "group%2Fsub%2Fapp")


class BriefRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_github_view_roundtrip(self):
        data = {
            "title": "Fix auth middleware",
            "body": "Continue the interceptor work.",
            "state": "OPEN",
            "author": {"login": "ada"},
            "baseRefName": "main",
            "headRefName": "fix/auth",
            "headRefOid": "abc1234deadbeef",
            "url": "https://github.com/acme/app/pull/9",
            "number": 9,
            "isDraft": True,
            "reviewDecision": "CHANGES_REQUESTED",
            "isCrossRepository": False,
            "files": [
                {
                    "path": "src/auth.ts",
                    "additions": 10,
                    "deletions": 2,
                    "changeType": "MODIFIED",
                }
            ],
            "commits": [
                {"messageHeadline": "wip auth", "oid": "abc1234deadbeef"}
            ],
            "reviews": [
                {
                    "body": "Please add a test.",
                    "state": "CHANGES_REQUESTED",
                    "author": {"login": "linus"},
                }
            ],
            "comments": [
                {"body": "I hit the usage limit mid-change.", "author": {"login": "ada"}}
            ],
            "labels": [{"name": "ready-for-agent"}],
            "closingIssuesReferences": [{"number": 3, "title": "Auth gap"}],
            "statusCheckRollup": [
                {"name": "tests", "conclusion": "FAILURE"},
            ],
        }
        inline = [
            {
                "body": "This leaks the token.",
                "user": {"login": "linus"},
                "path": "src/auth.ts",
                "line": 44,
            }
        ]
        brief = self.mod.brief_from_github_view(data, inline=inline, source="gh")
        text = self.mod.render(brief)
        self.assertIn("provider: github", text)
        self.assertIn("number: 9", text)
        self.assertIn("draft: true", text)
        self.assertIn("src/auth.ts (+10/-2)", text)
        self.assertIn("## Goal", text)
        self.assertIn("Continue the interceptor work.", text)
        self.assertIn("src/auth.ts:44 — linus", text)
        self.assertIn("This leaks the token.", text)
        self.assertIn("tests: FAILURE", text)
        self.assertIn("#3 Auth gap", text)
        self.assertIn("Continue the interrupted work from this brief.", text)
        self.assertIn("Changes Requested", text)

    def test_gitlab_brief(self):
        mr = {
            "iid": 7,
            "title": "Add cache",
            "description": "Cache the list endpoint.",
            "state": "opened",
            "draft": False,
            "author": {"username": "grace"},
            "source_branch": "feat/cache",
            "target_branch": "main",
            "sha": "def4567",
            "web_url": "https://gitlab.com/g/p/-/merge_requests/7",
            "labels": ["backend"],
            "head_pipeline": {"status": "failed", "web_url": "https://gitlab.com/p"},
        }
        discussions = [
            {
                "notes": [
                    {
                        "system": False,
                        "body": "Watch the TTL.",
                        "author": {"username": "reviewer"},
                        "position": {"new_path": "cache.py", "new_line": 12},
                    }
                ]
            }
        ]
        brief = self.mod.brief_from_gitlab(
            mr,
            changes=[{"new_path": "cache.py"}],
            discussions=discussions,
            commits=[{"short_id": "def4567", "title": "Add cache"}],
            source="api",
            host="gitlab.com",
        )
        text = self.mod.render(brief)
        self.assertIn("provider: gitlab", text)
        self.assertIn("head: feat/cache", text)
        self.assertIn("cache.py:12 — reviewer", text)
        self.assertIn("pipeline: failed", text)

    def test_bitbucket_brief(self):
        pr = {
            "id": 3,
            "title": "Docs",
            "description": "Fix the README.",
            "state": "OPEN",
            "author": {"display_name": "Pat"},
            "source": {
                "branch": {"name": "docs"},
                "commit": {"hash": "aaa111"},
            },
            "destination": {"branch": {"name": "master"}},
            "links": {"html": {"href": "https://bitbucket.org/w/r/pull-requests/3"}},
        }
        brief = self.mod.brief_from_bitbucket(
            pr,
            comments=[
                {
                    "content": {"raw": "typo on line 1"},
                    "user": {"display_name": "Kim"},
                    "inline": {"path": "README.md", "to": 1},
                }
            ],
            diffstat=[
                {
                    "new": {"path": "README.md"},
                    "lines_added": 2,
                    "lines_removed": 1,
                    "status": "modified",
                }
            ],
        )
        text = self.mod.render(brief)
        self.assertIn("provider: bitbucket", text)
        self.assertIn("README.md:1 — Kim", text)
        self.assertIn("README.md (+2/-1)", text)

    def test_ending_draft_without_comments(self):
        brief = self.mod.Brief(
            provider="github",
            url="https://example.com/pull/1",
            number="1",
            title="WIP",
            state="open",
            author="ada",
            draft=True,
        )
        self.assertIn("Draft", self.mod.ending_text(brief))

    def test_cli_help(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.main(["--help"])
        self.assertIn(ctx.exception.code, (0, None))


class CliFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_unparsed_argument_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.main(["not a pr"])
        self.assertIn("pull/merge request URL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
