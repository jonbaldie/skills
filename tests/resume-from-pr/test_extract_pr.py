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

    def test_azure_devops_project_omitted(self):
        t = self.parse(
            "https://dev.azure.com/myorg/_git/myrepo/pullrequest/123"
        )
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.host, "dev.azure.com")
        self.assertEqual(t.org, "myorg")
        self.assertEqual(t.project, "myorg")
        self.assertEqual(t.repo, "myrepo")
        self.assertEqual(t.number, "123")

    def test_azure_visualstudio_project_omitted(self):
        t = self.parse(
            "https://myorg.visualstudio.com/_git/myrepo/pullrequest/124"
        )
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.org, "myorg")
        self.assertEqual(t.project, "myorg")
        self.assertEqual(t.repo, "myrepo")
        self.assertEqual(t.number, "124")

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

    def test_embedded_url_trailing_punctuation(self):
        for punct in ".,;:!?":
            t = self.mod.parse_argument(
                f"please resume https://github.com/owner/repo/pull/8{punct}"
            )
            self.assertEqual(t.number, "8", f"trailing {punct!r} leaked")
            self.assertEqual(t.url, f"https://github.com/owner/repo/pull/8")
        t = self.mod.parse_argument(
            "resume https://github.com/owner/repo/pull/8..."
        )
        self.assertEqual(t.url, "https://github.com/owner/repo/pull/8")

    def test_embedded_url_preserves_inner_punctuation(self):
        self.assertEqual(
            self.mod.first_url("see https://example.com/a.b/pull/8, done."),
            "https://example.com/a.b/pull/8",
        )
        self.assertEqual(
            self.mod.first_url("check https://host/x?q=1. next"),
            "https://host/x?q=1",
        )

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

    def test_reviews_and_comments_interleave_chronologically(self):
        """Issue #65: a maintainer comment at 11:00 and a review at 12:00 must
        interleave by timestamp; the Ending must be the newer review."""
        data = {
            "title": "Fix auth middleware",
            "body": "",
            "state": "OPEN",
            "author": {"login": "ada"},
            "url": "https://github.com/acme/app/pull/5",
            "number": 5,
            "reviews": [
                {
                    "body": "Looks good now.",
                    "state": "COMMENTED",
                    "author": {"login": "linus"},
                    "submittedAt": "2026-01-01T12:00:00Z",
                }
            ],
            "comments": [
                {
                    "body": "I hit the usage limit mid-change.",
                    "author": {"login": "ada"},
                    "createdAt": "2026-01-01T11:00:00Z",
                }
            ],
        }
        brief = self.mod.brief_from_github_view(data)
        text = self.mod.render(brief)
        discussion = text.split("## Discussion", 1)[1].split("## Checks", 1)[0]
        self.assertLess(
            discussion.index("Comment — ada"),
            discussion.index("Review — linus"),
            "Discussion must list events chronologically, not grouped by kind",
        )
        ending = self.mod.ending_text(brief)
        self.assertIn("linus", ending)
        self.assertIn("Looks good now.", ending)
        self.assertNotIn("ada", ending)

    def test_events_without_timestamps_keep_stable_position(self):
        """Issue #65: undated events must not disturb the chronological order
        of timestamped events, and keep their own relative order."""
        comment = lambda kind, body, created: self.mod.Comment(  # noqa: E731
            author="u", body=body, created=created, kind=kind
        )
        brief = self.mod.Brief(
            provider="github",
            url="https://example.com/pull/1",
            number="1",
            title="T",
            state="open",
            author="ada",
            comments=[
                comment("review", "review at noon", "2026-01-01T12:00:00Z"),
                comment("discussion", "undated comment", None),
                comment("review", "review at ten", "2026-01-01T10:00:00Z"),
            ],
        )
        events = self.mod.chronological_events(brief.comments)
        bodies = [e.body for e in events if e.created]
        self.assertEqual(
            bodies, ["review at ten", "review at noon"], "timestamped order broken"
        )
        self.assertEqual(
            [e.body for e in events][-2:],
            ["review at ten", "review at noon"],
            "undated event disturbed timestamped ordering",
        )

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


class BareNumberResolutionTests(unittest.TestCase):
    """Bare-number lookup against the current git remote (issue #62)."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def patch_run_cmd(self, remotes_output, branch=None):
        mod = self.mod
        original = mod.run_cmd

        def fake(argv, cwd=None, timeout=45):
            key = " ".join(argv)
            if key.startswith("git remote -v"):
                return remotes_output
            if key.startswith("git rev-parse"):
                if branch is None:
                    raise mod.Skip("no branch")
                return branch
            raise mod.Skip(f"unmocked command: {argv}")

        mod.run_cmd = fake
        self.addCleanup(setattr, mod, "run_cmd", original)

    def patch_http_json(self, handler):
        mod = self.mod
        original = mod.http_json
        mod.http_json = handler
        self.addCleanup(setattr, mod, "http_json", original)

    def test_resolve_number_azure_devops_remote(self):
        self.patch_run_cmd(
            "origin\thttps://org@dev.azure.com/org/project/_git/repo (fetch)\n"
        )
        t = self.mod.resolve_number("15", "workspace")
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.org, "org")
        self.assertEqual(t.project, "project")
        self.assertEqual(t.repo, "repo")
        self.assertEqual(t.number, "15")
        self.assertIn("/pullrequest/15", t.url)

    def test_resolve_number_azure_visualstudio_remote(self):
        self.patch_run_cmd(
            "origin\thttps://contoso@contoso.visualstudio.com/proj/_git/repo (fetch)\n"
        )
        t = self.mod.resolve_number("2", "workspace")
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.org, "contoso")
        self.assertEqual(t.project, "proj")
        self.assertIn("/pullrequest/2", t.url)

    def test_resolve_number_azure_ssh_remote(self):
        self.patch_run_cmd("origin\tgit@ssh.dev.azure.com:v3/org/project/repo\n")
        t = self.mod.resolve_number("7", "workspace")
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.org, "org")
        self.assertEqual(t.project, "project")
        self.assertEqual(t.repo, "repo")

    def test_resolve_number_bitbucket_server_remote(self):
        self.patch_run_cmd(
            "origin\thttps://git.example.com/projects/KEY/repos/slug.git (fetch)\n"
        )
        t = self.mod.resolve_number("4", "workspace")
        self.assertEqual(t.provider, "bitbucket-server")
        self.assertEqual(t.owner, "KEY")
        self.assertEqual(t.repo, "slug")

    def test_resolve_number_bitbucket_server_scm_remote(self):
        self.patch_run_cmd("origin\thttps://git.example.com/scm/KEY/slug.git (fetch)\n")
        t = self.mod.resolve_number("4", "workspace")
        self.assertEqual(t.provider, "bitbucket-server")

    def test_resolve_number_keeps_unknown_provider_fallback(self):
        self.patch_run_cmd("origin\thttps://ghe.example.com/acme/app.git (fetch)\n")
        t = self.mod.resolve_number("9", "workspace")
        self.assertEqual(t.provider, "unknown")
        self.assertEqual(t.host, "ghe.example.com")

    def test_current_branch_azure_resolves(self):
        self.patch_run_cmd(
            "origin\thttps://org@dev.azure.com/org/project/_git/repo (fetch)\n",
            branch="feature/x",
        )
        self.patch_http_json(
            lambda url, headers=None, timeout=30: {
                "value": [
                    {
                        "pullRequestId": 15,
                        "repository": {"name": "repo", "project": {"name": "project"}},
                    }
                ]
            }
        )
        t = self.mod.resolve_current_branch("workspace")
        self.assertEqual(t.provider, "azure")
        self.assertEqual(t.number, "15")
        self.assertEqual(t.project, "project")

    def test_current_branch_azure_auth_failure_names_provider(self):
        self.patch_run_cmd(
            "origin\thttps://org@dev.azure.com/org/project/_git/repo (fetch)\n",
            branch="feature/x",
        )

        def fail(url, headers=None, timeout=30):
            raise self.mod.FetchError("HTTP 401 for https://dev.azure.com/…")

        self.patch_http_json(fail)
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.resolve_current_branch("workspace")
        message = str(ctx.exception)
        self.assertIn("Azure DevOps", message)
        self.assertIn("feature/x", message)
        self.assertIn("AZURE_DEVOPS_TOKEN", message)

    def test_current_branch_gitea_resolves(self):
        self.patch_run_cmd(
            "origin\thttps://codeberg.org/owner/repo.git (fetch)\n", branch="feature/x"
        )
        self.patch_http_json(
            lambda url, headers=None, timeout=30: [
                {
                    "number": 9,
                    "html_url": "https://codeberg.org/owner/repo/pulls/9",
                    "head": {"ref": "feature/x", "repo": {"full_name": "owner/repo"}},
                }
            ]
        )
        t = self.mod.resolve_current_branch("workspace")
        self.assertEqual(t.provider, "gitea")
        self.assertEqual(t.number, "9")

    def test_current_branch_bitbucket_resolves(self):
        self.patch_run_cmd(
            "origin\thttps://bitbucket.org/workspace/repo.git (fetch)\n",
            branch="docs",
        )
        self.patch_http_json(
            lambda url, headers=None, timeout=30: {
                "values": [
                    {
                        "id": 3,
                        "links": {
                            "html": {"href": "https://bitbucket.org/w/r/pull-requests/3"}
                        },
                    }
                ]
            }
        )
        t = self.mod.resolve_current_branch("workspace")
        self.assertEqual(t.provider, "bitbucket")
        self.assertEqual(t.number, "3")

    def test_current_branch_bitbucket_server_resolves(self):
        self.patch_run_cmd(
            "origin\thttps://git.example.com/projects/KEY/repos/slug.git (fetch)\n",
            branch="feature/x",
        )
        self.patch_http_json(
            lambda url, headers=None, timeout=30: {"values": [{"id": 4}]}
        )
        t = self.mod.resolve_current_branch("workspace")
        self.assertEqual(t.provider, "bitbucket-server")
        self.assertEqual(t.number, "4")

    def test_current_branch_github_without_gh_names_provider(self):
        self.patch_run_cmd(
            "origin\thttps://github.com/acme/app.git (fetch)\n", branch="fix/auth"
        )
        self.patch_http_json(lambda url, headers=None, timeout=30: [])
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.resolve_current_branch("workspace")
        message = str(ctx.exception)
        self.assertIn("GitHub", message)
        self.assertIn("fix/auth", message)

    def test_current_branch_unknown_host_keeps_generic_error(self):
        self.patch_run_cmd("origin\thttps://git.example.com/foo/bar (fetch)\n")
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.resolve_current_branch("workspace")
        self.assertIn("No open pull/merge request for the current branch", str(ctx.exception))

    def test_current_branch_detached_head_names_blocker(self):
        self.patch_run_cmd(
            "origin\thttps://org@dev.azure.com/org/project/_git/repo (fetch)\n",
            branch="HEAD",
        )
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.resolve_current_branch("workspace")
        message = str(ctx.exception)
        self.assertIn("Azure DevOps", message)
        self.assertIn("current branch", message)


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
