#!/usr/bin/env python3
"""Unit tests for resume-from-pr extract-pr.py (no live network)."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
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

    def test_gitea_path_shape_on_other_hosts(self):
        t = self.parse("https://git.example.com/owner/repo/pulls/9")
        self.assertEqual(t.provider, "gitea")
        self.assertEqual(t.host, "git.example.com")
        self.assertEqual(t.number, "9")

    def test_github_pulls_path_shape(self):
        t = self.parse("https://github.com/jonbaldie/skills/pulls/90")
        self.assertEqual(t.provider, "github")
        self.assertEqual(t.host, "github.com")
        self.assertEqual(t.owner, "jonbaldie")
        self.assertEqual(t.repo, "skills")
        self.assertEqual(t.number, "90")
        self.assertEqual(t.slug, "jonbaldie/skills")

    def test_github_www_pulls_path_shape(self):
        t = self.parse("https://www.github.com/jonbaldie/skills/pulls/90")
        self.assertEqual(t.provider, "github")
        self.assertEqual(t.host, "www.github.com")
        self.assertEqual(t.number, "90")

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

    def test_embedded_url_quotes_and_backticks(self):
        cases = [
            'resume "https://github.com/owner/repo/pull/8"',
            "resume 'https://github.com/owner/repo/pull/8'",
            "resume `https://github.com/owner/repo/pull/8`",
        ]
        for arg in cases:
            t = self.mod.parse_argument(arg)
            self.assertEqual(t.number, "8", f"failed parsing number from {arg!r}")
            self.assertEqual(
                t.url,
                "https://github.com/owner/repo/pull/8",
                f"trailing quote/backtick leaked from {arg!r}",
            )

    def test_embedded_url_trailing_quotes_with_punctuation(self):
        cases = [
            'see "https://github.com/owner/repo/pull/8", thanks',
            "see 'https://github.com/owner/repo/pull/8.' next",
            "see `https://github.com/owner/repo/pull/8`? next",
            '("https://github.com/owner/repo/pull/8")',
            "('https://github.com/owner/repo/pull/8')",
            "(`https://github.com/owner/repo/pull/8`)",
        ]
        for arg in cases:
            t = self.mod.parse_argument(arg)
            self.assertEqual(t.number, "8", f"failed parsing number from {arg!r}")
            self.assertEqual(
                t.url,
                "https://github.com/owner/repo/pull/8",
                f"malformed url from {arg!r}",
            )

    def test_wrapped_single_quotes_and_backticks(self):
        t = self.mod.parse_argument("'https://github.com/owner/repo/pull/8'")
        self.assertEqual(t.number, "8")
        self.assertEqual(t.url, "https://github.com/owner/repo/pull/8")
        t = self.mod.parse_argument("`https://github.com/owner/repo/pull/8`")
        self.assertEqual(t.number, "8")
        self.assertEqual(t.url, "https://github.com/owner/repo/pull/8")

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


class ProviderTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_identify_known_hosts(self):
        cases = {
            "github.com": "github",
            "WWW.GitHub.com": "github",
            "gitlab.com": "gitlab",
            "gitlab.example.com": "gitlab",
            "bitbucket.org": "bitbucket",
            "dev.azure.com": "azure",
            "ssh.dev.azure.com": "azure",
            "acme.visualstudio.com": "azure",
            "codeberg.org": "gitea",
            "git.forgejo.dev": "gitea",
            "example.com": "unknown",
            "ghe.example.com": "unknown",
        }
        for host, provider in cases.items():
            with self.subTest(host=host):
                self.assertEqual(self.mod.identify(host), provider)

    def test_parse_target_returns_none_for_non_pr_text(self):
        self.assertIsNone(self.mod.parse_target("https://example.com/not-a-pr"))
        self.assertIsNone(self.mod.parse_target("not a pr"))

    def test_parse_target_parses_pr_url(self):
        t = self.mod.parse_target("https://codeberg.org/owner/repo/pulls/3")
        self.assertEqual(t.provider, "gitea")
        self.assertEqual(t.number, "3")
        self.assertEqual(t.slug, "owner/repo")

    def test_every_provider_is_fully_wired(self):
        for provider in self.mod.PROVIDERS:
            with self.subTest(provider=provider.name):
                self.assertTrue(self.mod.PROVIDER_LABELS.get(provider.name))
                self.assertTrue(self.mod.PROVIDER_TOKEN_HINTS.get(provider.name))
                self.assertTrue(self.mod.FETCHERS.get(provider.name))
                self.assertIn(provider.name, self.mod.BRANCH_LOOKUPS)
        wired = {provider.name for provider in self.mod.PROVIDERS}
        self.assertEqual(set(self.mod.FETCHERS) - {"unknown"}, wired)

    def test_url_precedence_is_declared_and_unambiguous(self):
        precedences = [
            shape.precedence
            for provider in self.mod.PROVIDERS
            for shape in provider.url_shapes
        ]
        self.assertEqual(len(precedences), len(set(precedences)))
        host_precedences = [p.host_precedence for p in self.mod.PROVIDERS]
        self.assertEqual(len(host_precedences), len(set(host_precedences)))

    def test_new_table_entry_wires_host_and_url_matching(self):
        mod = self.mod
        forge = mod.Provider(
            name="example-forge",
            label="Example Forge",
            token_hint="set EXAMPLE_TOKEN",
            host_pattern=r"forge\.example",
            host_precedence=5,
            url_shapes=(
                mod.UrlShape(
                    precedence=1,
                    pattern=r"^https?://(?P<host>forge\.example)/(?P<owner>[^/]+)"
                    r"/(?P<repo>[^/]+)/change/(?P<num>\d+)",
                ),
            ),
            from_remote=lambda host, path, number: mod.Target(
                provider="example-forge", host=host, number=number
            ),
        )
        original = mod.PROVIDERS
        mod.PROVIDERS = original + (forge,)
        try:
            self.assertEqual(mod.identify("forge.example"), "example-forge")
            t = mod.parse_pr_url("https://forge.example/acme/app/change/4")
            self.assertEqual(t.provider, "example-forge")
            self.assertEqual(t.slug, "acme/app")
            self.assertEqual(t.number, "4")
            t = mod.target_from_remote("4", "git@forge.example:acme/app.git")
            self.assertEqual(t.provider, "example-forge")
        finally:
            mod.PROVIDERS = original


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

    def test_rest_issue_comment_author_comes_from_user(self):
        """Issue #162: REST issue comments carry the author under `user`."""
        brief = self.mod.brief_from_github_rest(
            {"number": 5, "title": "T", "state": "open", "user": {"login": "linus"}},
            issue_comments=[
                {
                    "body": "x",
                    "user": {"login": "ada"},
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ],
        )
        self.assertEqual([c.author for c in brief.comments], ["ada"])
        self.assertTrue(self.mod.ending_text(brief).startswith("ada: "))
        self.assertIn("### Comment — ada", self.mod.render(brief))

    def test_gh_view_comment_author_still_resolves(self):
        brief = self.mod.brief_from_github_view(
            {
                "title": "T",
                "number": 5,
                "comments": [{"body": "x", "author": {"login": "ada"}}],
            }
        )
        self.assertEqual([c.author for c in brief.comments], ["ada"])

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



class FakeForge:
    """Serve canned JSON through urlopen, paging the way the real host does."""

    def __init__(self, testcase, mod):
        self.mod = mod
        self.routes = {}
        self.requests = []
        original = mod.urllib.request.urlopen
        mod.urllib.request.urlopen = self.urlopen
        testcase.addCleanup(setattr, mod.urllib.request, "urlopen", original)

    def route(self, url, handler):
        self.routes[url] = handler

    def requested(self, url):
        """Query dicts of every request made for one route."""
        return [
            dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(r).query))
            for r in self.requests
            if r.split("?", 1)[0] == url
        ]

    def urlopen(self, request, timeout=30):
        url = request.full_url
        self.requests.append(url)
        parts = urllib.parse.urlsplit(url)
        key = f"{parts.scheme}://{parts.netloc}{parts.path}"
        handler = self.routes.get(key)
        if handler is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b"{}"))
        query = dict(urllib.parse.parse_qsl(parts.query))
        result = handler(key, query)
        if isinstance(result, int):
            raise urllib.error.HTTPError(
                url, result, "error", {}, io.BytesIO(b'{"message": "denied"}')
            )
        body, headers = result
        return _FakeResponse(json.dumps(body), headers)


class _FakeResponse:
    def __init__(self, text, headers):
        self._text = text
        self.headers = headers

    def read(self):
        return self._text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def single(body):
    return lambda key, query: (body, {})


def status(code):
    return lambda key, query: code


def link_pager(items, size_param, default, maximum, wrap=None):
    """GitHub/GitLab/Gitea: page + size params, next page in a Link header."""

    def handler(key, query):
        size = min(int(query.get(size_param, default)), maximum)
        page = int(query.get("page", 1))
        chunk = items[(page - 1) * size : page * size]
        headers = {}
        if page * size < len(items):
            nxt = dict(query, page=str(page + 1))
            headers["Link"] = (
                f'<{key}?{urllib.parse.urlencode(nxt)}>; rel="next", '
                f'<{key}?page=1>; rel="first"'
            )
        return ({wrap: chunk} if wrap else chunk), headers

    return handler


def bitbucket_pager(items, maximum):
    """Bitbucket Cloud: pagelen + page params, next page URL in "next"."""

    def handler(key, query):
        size = min(int(query.get("pagelen", 10)), maximum)
        page = int(query.get("page", 1))
        body = {"values": items[(page - 1) * size : page * size], "pagelen": size}
        if page * size < len(items):
            nxt = dict(query, page=str(page + 1))
            body["next"] = f"{key}?{urllib.parse.urlencode(nxt)}"
        return body, {}

    return handler


def bitbucket_server_pager(items, maximum):
    """Bitbucket Server: limit + start params, isLastPage/nextPageStart."""

    def handler(key, query):
        size = min(int(query.get("limit", 25)), maximum)
        start = int(query.get("start", 0))
        chunk = items[start : start + size]
        last = start + size >= len(items)
        body = {"values": chunk, "isLastPage": last, "start": start}
        if not last:
            body["nextPageStart"] = start + size
        return body, {}

    return handler


def azure_pager(items, size):
    """Azure DevOps: continuationToken param, token in a response header."""

    def handler(key, query):
        start = int(query.get("continuationToken", 0))
        chunk = items[start : start + size]
        headers = {}
        if start + size < len(items):
            headers["x-ms-continuationtoken"] = str(start + size)
        return {"value": chunk, "count": len(chunk)}, headers

    return handler


def stamp(n):
    return f"2026-01-01T{n // 60:02d}:{n % 60:02d}:00Z"


class CollectionPagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def setUp(self):
        self.forge = FakeForge(self, self.mod)

    def github_forge(
        self, *, comments, maximum=30, reviews=None, check_runs=None, body=None
    ):
        api = "https://api.github.com/repos/acme/app"
        base = f"{api}/pulls/9"
        self.forge.route(
            base,
            single(
                {
                    "number": 9,
                    "title": "Long PR",
                    "state": "open",
                    "user": {"login": "ada"},
                    "html_url": "https://github.com/acme/app/pull/9",
                    "head": {"ref": "feat", "sha": "abc1234"},
                    "base": {"ref": "main"},
                    "body": body,
                }
            ),
        )
        for path in ("files", "comments", "commits"):
            self.forge.route(f"{base}/{path}", link_pager([], "per_page", 30, maximum))
        self.forge.route(
            f"{base}/reviews",
            reviews or link_pager([], "per_page", 30, maximum),
        )
        self.forge.route(
            f"{api}/issues/9/comments",
            link_pager(comments, "per_page", 30, maximum),
        )
        self.forge.route(
            f"{api}/commits/abc1234/status",
            link_pager([], "per_page", 30, maximum, wrap="statuses"),
        )
        self.forge.route(
            f"{api}/commits/abc1234/check-runs",
            check_runs or link_pager([], "per_page", 30, maximum, wrap="check_runs"),
        )
        return self.mod.parse_pr_url("https://github.com/acme/app/pull/9")

    def numbered_comments(self, count):
        return [
            {
                "body": f"comment {n}",
                "user": {"login": "ada"},
                "created_at": stamp(n),
            }
            for n in range(1, count + 1)
        ]

    def test_github_ending_reports_the_last_of_45_comments(self):
        target = self.github_forge(comments=self.numbered_comments(45))
        brief = self.mod.fetch_github_api(target)
        self.assertEqual(self.mod.ending_text(brief), "ada: comment 45")
        pages = self.forge.requested("https://api.github.com/repos/acme/app/issues/9/comments")
        self.assertEqual(len(pages), 2)

    def test_github_collects_every_page_with_page_params(self):
        target = self.github_forge(comments=self.numbered_comments(5), maximum=2)
        brief = self.mod.fetch_github_api(target)
        bodies = [c.body for c in brief.comments]
        self.assertEqual(bodies, [f"comment {n}" for n in range(1, 6)])
        pages = self.forge.requested("https://api.github.com/repos/acme/app/issues/9/comments")
        self.assertEqual([p.get("per_page") for p in pages], ["100"] * 3)
        self.assertEqual([p.get("page") for p in pages], [None, "2", "3"])
        self.assertEqual(brief.notes, [])

    def test_page_cap_notes_truncation_in_rendered_brief(self):
        cap = self.mod.MAX_COLLECTION_PAGES
        target = self.github_forge(comments=self.numbered_comments(cap + 3), maximum=1)
        brief = self.mod.fetch_github_api(target)
        self.assertEqual(len(brief.comments), cap)
        text = self.mod.render(brief)
        self.assertIn("## Gaps", text)
        self.assertRegex(text, r"issue comments: truncated")

    def test_failed_collection_is_named_and_brief_still_renders(self):
        target = self.github_forge(
            comments=self.numbered_comments(2), reviews=status(403)
        )
        brief = self.mod.fetch_github_api(target)
        text = self.mod.render(brief)
        self.assertRegex(text, r"## Ending\n.*: comment 2\n")
        self.assertIn("## Gaps", text)
        self.assertRegex(text, r"reviews: .*HTTP 403")

    def test_github_actions_check_runs_appear_in_api_brief(self):
        runs = [
            {"name": f"build ({os})", "status": "completed", "conclusion": "failure"}
            for os in ("ubuntu-latest", "windows-latest", "macos-latest")
        ]
        runs.append({"name": "lint", "status": "in_progress", "conclusion": None})
        target = self.github_forge(
            comments=[],
            maximum=2,
            check_runs=link_pager(runs, "per_page", 30, 2, wrap="check_runs"),
        )
        brief = self.mod.fetch_github_api(target)
        text = self.mod.render(brief)
        self.assertIn(
            "## Checks\n"
            "- build (ubuntu-latest): FAILURE\n"
            "- build (windows-latest): FAILURE\n"
            "- build (macos-latest): FAILURE\n"
            "- lint: IN_PROGRESS\n",
            text,
        )
        self.assertRegex(text, r"## Ending\nFailing checks: build \(ubuntu-latest\)")
        self.assertEqual(brief.notes, [])

    def test_github_check_run_failure_is_a_named_gap(self):
        target = self.github_forge(comments=[], check_runs=status(403))
        text = self.mod.render(self.mod.fetch_github_api(target))
        self.assertIn("## Gaps", text)
        self.assertRegex(text, r"check runs: .*HTTP 403")

    def test_github_no_checks_has_no_gap(self):
        target = self.github_forge(comments=[])
        text = self.mod.render(self.mod.fetch_github_api(target))
        self.assertNotIn("## Checks", text)
        self.assertNotIn("## Gaps", text)

    def test_github_api_brief_links_issues_closed_by_the_body(self):
        target = self.github_forge(
            comments=[],
            body="Closes #159.\nAlso fixes: other/repo#7, see #8, resolved #159",
        )
        text = self.mod.render(self.mod.fetch_github_api(target))
        self.assertIn("## Linked issues\n- #159\n- other/repo#7\n", text)
        self.assertNotIn("- #8", text)

    def test_gitlab_collects_every_page(self):
        root = "https://gitlab.com/api/v4/projects/team%2Fapp/merge_requests/3"
        self.forge.route(
            root,
            single({"iid": 3, "title": "MR", "state": "opened", "author": {"username": "ada"}}),
        )
        diffs = [{"new_path": f"f{n}.py"} for n in range(5)]
        discussions = [
            {"notes": [{"body": f"note {n}", "author": {"username": "ada"}, "created_at": stamp(n)}]}
            for n in range(5)
        ]
        commits = [{"id": f"{n:07d}", "title": f"commit {n}"} for n in range(5)]
        self.forge.route(f"{root}/diffs", link_pager(diffs, "per_page", 20, 2))
        self.forge.route(f"{root}/discussions", link_pager(discussions, "per_page", 20, 2))
        self.forge.route(f"{root}/commits", link_pager(commits, "per_page", 20, 2))
        target = self.mod.parse_pr_url("https://gitlab.com/team/app/-/merge_requests/3")
        brief = self.mod.fetch_gitlab_api(target)
        self.assertEqual([f.path for f in brief.files], [f"f{n}.py" for n in range(5)])
        self.assertEqual(len(brief.comments), 5)
        self.assertEqual(len(brief.commits), 5)
        pages = self.forge.requested(f"{root}/discussions")
        self.assertEqual([p.get("per_page") for p in pages], ["100"] * 3)
        self.assertEqual([p.get("page") for p in pages], [None, "2", "3"])
        self.assertEqual(brief.notes, [])

    def test_gitea_collects_every_page(self):
        root = "https://codeberg.org/api/v1/repos/owner/repo/pulls/9"
        self.forge.route(
            root,
            single({"number": 9, "title": "PR", "state": "open", "user": {"login": "ada"}}),
        )
        files = [{"filename": f"f{n}.go"} for n in range(5)]
        self.forge.route(f"{root}/files", link_pager(files, "limit", 30, 2))
        self.forge.route(f"{root}/reviews", link_pager([], "limit", 30, 2))
        self.forge.route(
            "https://codeberg.org/api/v1/repos/owner/repo/issues/9/comments",
            link_pager(self.numbered_comments(5), "limit", 30, 2),
        )
        target = self.mod.parse_pr_url("https://codeberg.org/owner/repo/pulls/9")
        brief = self.mod.fetch_gitea_api(target)
        self.assertEqual(len(brief.files), 5)
        self.assertEqual(len(brief.comments), 5)
        self.assertEqual({c.author for c in brief.comments}, {"ada"})
        pages = self.forge.requested(f"{root}/files")
        self.assertEqual([p.get("limit") for p in pages], ["50"] * 3)
        self.assertEqual([p.get("page") for p in pages], [None, "2", "3"])
        self.assertEqual(brief.notes, [])

    def test_bitbucket_cloud_collects_every_page(self):
        root = "https://api.bitbucket.org/2.0/repositories/ws/repo/pullrequests/11"
        self.forge.route(
            root,
            single({"id": 11, "title": "PR", "state": "OPEN", "author": {"display_name": "Ada"}}),
        )
        comments = [
            {"content": {"raw": f"comment {n}"}, "user": {"display_name": "Ada"}, "created_on": stamp(n)}
            for n in range(5)
        ]
        diffstat = [{"new": {"path": f"f{n}"}, "status": "modified"} for n in range(5)]
        statuses = [{"name": f"ci {n}", "state": "SUCCESSFUL"} for n in range(5)]
        self.forge.route(f"{root}/comments", bitbucket_pager(comments, 2))
        self.forge.route(f"{root}/diffstat", bitbucket_pager(diffstat, 2))
        self.forge.route(f"{root}/statuses", bitbucket_pager(statuses, 2))
        target = self.mod.parse_pr_url("https://bitbucket.org/ws/repo/pull-requests/11")
        brief = self.mod.fetch_bitbucket_api(target)
        self.assertEqual(len(brief.comments), 5)
        self.assertEqual(len(brief.files), 5)
        self.assertEqual(len(brief.checks), 5)
        pages = self.forge.requested(f"{root}/comments")
        self.assertEqual([p.get("pagelen") for p in pages], ["50"] * 3)
        self.assertEqual([p.get("page") for p in pages], [None, "2", "3"])
        self.assertEqual(brief.notes, [])

    def test_bitbucket_server_collects_every_page(self):
        root = (
            "https://git.example.com/rest/api/1.0/projects/KEY/repos/slug/pull-requests/4"
        )
        self.forge.route(
            root,
            single({"id": 4, "title": "PR", "state": "OPEN", "author": {"user": {"name": "ada"}}}),
        )
        changes = [{"path": {"toString": f"f{n}"}, "type": "MODIFY"} for n in range(5)]
        activities = [
            {"comment": {"text": f"comment {n}", "author": {"name": "ada"}, "createdDate": n}}
            for n in range(5)
        ]
        self.forge.route(f"{root}/changes", bitbucket_server_pager(changes, 2))
        self.forge.route(f"{root}/activities", bitbucket_server_pager(activities, 2))
        target = self.mod.parse_pr_url(
            "https://git.example.com/projects/KEY/repos/slug/pull-requests/4"
        )
        brief = self.mod.fetch_bitbucket_server_api(target)
        self.assertEqual(len(brief.files), 5)
        self.assertEqual(len(brief.comments), 5)
        pages = self.forge.requested(f"{root}/activities")
        self.assertEqual([p.get("limit") for p in pages], ["100"] * 3)
        self.assertEqual([p.get("start") for p in pages], [None, "2", "4"])
        self.assertEqual(brief.notes, [])

    def test_azure_collects_every_page(self):
        root = (
            "https://dev.azure.com/org/project/_apis/git/repositories/repo/pullrequests/15"
        )
        self.forge.route(
            root,
            single({"pullRequestId": 15, "title": "PR", "status": "active"}),
        )
        threads = [
            {"comments": [{"content": f"comment {n}", "author": {"displayName": "Ada"}, "publishedDate": stamp(n)}]}
            for n in range(5)
        ]
        statuses = [{"context": {"name": f"ci {n}"}, "state": "succeeded"} for n in range(5)]
        self.forge.route(f"{root}/threads", azure_pager(threads, 2))
        self.forge.route(f"{root}/statuses", azure_pager(statuses, 2))
        target = self.mod.parse_pr_url(
            "https://dev.azure.com/org/project/_git/repo/pullrequest/15"
        )
        brief = self.mod.fetch_azure_api(target)
        self.assertEqual(len(brief.comments), 5)
        self.assertEqual(len(brief.checks), 5)
        pages = self.forge.requested(f"{root}/threads")
        self.assertEqual([p.get("api-version") for p in pages], ["7.1"] * 3)
        self.assertEqual(
            [p.get("continuationToken") for p in pages], [None, "2", "4"]
        )
        self.assertEqual(brief.notes, [])


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
