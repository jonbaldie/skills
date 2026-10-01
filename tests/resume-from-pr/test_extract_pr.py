#!/usr/bin/env python3
"""Unit tests for resume-from-pr extract-pr.py (no live network)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


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


def query_of(url: str) -> dict[str, str]:
    return {k: v[-1] for k, v in parse_qs(urlsplit(url).query).items()}


def numbered_comments(count: int) -> list[dict]:
    return [
        {
            "body": f"comment {i}",
            "user": {"login": "ada"},
            "created_at": f"2026-01-01T{i // 60:02d}:{i % 60:02d}:00Z",
        }
        for i in range(1, count + 1)
    ]


class FakeTransport:
    """Stand-in for http_request: routes by URL path suffix, records requests."""

    def __init__(self, routes):
        self.routes = routes
        self.requests: list[str] = []

    def __call__(self, url, headers=None, timeout=30):
        self.requests.append(url)
        path = urlsplit(url).path
        for suffix, handler in self.routes.items():
            if path.endswith(suffix):
                return handler(url)
        return [], {}

    def requested(self, suffix: str) -> list[str]:
        return [u for u in self.requests if urlsplit(u).path.endswith(suffix)]


def link_pages(items, size_param, page_param="page", server_max=30):
    """Serve items the way GitHub, GitLab, and Gitea do: Link rel="next"."""

    def handler(url):
        query = query_of(url)
        size = min(int(query.get(size_param, server_max)), server_max)
        page = int(query.get(page_param, 1))
        chunk = items[(page - 1) * size : page * size]
        headers = {}
        if page * size < len(items):
            parts = urlsplit(url)
            nxt = dict(query, **{page_param: str(page + 1)})
            next_url = urlunsplit(parts._replace(query=urlencode(nxt)))
            headers["link"] = f'<{next_url}>; rel="next", <{url}>; rel="first"'
        return chunk, headers

    return handler


class CollectionPagingTests(unittest.TestCase):
    """Issue #159: every API fetcher pages PR collections and reports gaps."""

    def setUp(self):
        self.mod = load_mod()

    def patch_transport(self, routes):
        fake = FakeTransport(routes)
        original = self.mod.http_request
        self.mod.http_request = fake
        self.addCleanup(setattr, self.mod, "http_request", original)
        return fake

    def github_target(self):
        return self.mod.parse_pr_url("https://github.com/o/r/pull/7")

    def github_routes(self, **overrides):
        routes = {
            "/pulls/7": lambda url: (
                {"number": 7, "title": "T", "state": "open", "user": {"login": "ada"}},
                {},
            ),
            "/issues/7/comments": link_pages(numbered_comments(45), "per_page"),
        }
        routes.update(overrides)
        return routes

    def test_github_long_discussion_ends_on_newest_comment(self):
        fake = self.patch_transport(self.github_routes())
        brief = self.mod.fetch_github_api(self.github_target())
        self.assertEqual(len([c for c in brief.comments if c.kind == "discussion"]), 45)
        self.assertIn("comment 45", self.mod.ending_text(brief))
        pages = fake.requested("/issues/7/comments")
        self.assertEqual(len(pages), 2)
        self.assertEqual(query_of(pages[0]).get("per_page"), "100")
        self.assertEqual(query_of(pages[1]).get("page"), "2")


    def test_page_cap_is_reported_in_rendered_brief(self):
        self.patch_transport(self.github_routes())
        original = self.mod.MAX_COLLECTION_PAGES
        self.mod.MAX_COLLECTION_PAGES = 1
        self.addCleanup(setattr, self.mod, "MAX_COLLECTION_PAGES", original)
        text = self.mod.render(self.mod.fetch_github_api(self.github_target()))
        gaps = text.split("## Missing data", 1)[1].split("##", 1)[0]
        self.assertIn("discussion comments: truncated after 1 pages", gaps)

    def test_failed_collection_is_named_and_rest_still_renders(self):
        def forbidden(url):
            raise self.mod.FetchError(f"HTTP 403 for {url}: rate limited")

        routes = self.github_routes(**{"/pulls/7/comments": forbidden})
        self.patch_transport(routes)
        brief = self.mod.fetch_github_api(self.github_target())
        text = self.mod.render(brief)
        gaps = text.split("## Missing data", 1)[1].split("##", 1)[0]
        self.assertIn("review comments: request failed", gaps)
        self.assertIn("HTTP 403", gaps)
        self.assertIn("comment 45", text.split("## Ending", 1)[1])

    def test_complete_brief_has_no_missing_data_section(self):
        self.patch_transport(self.github_routes())
        text = self.mod.render(self.mod.fetch_github_api(self.github_target()))
        self.assertNotIn("## Missing data", text)

    def test_gitlab_follows_link_header(self):
        notes = [
            {"notes": [{"body": f"note {i}", "author": {"username": "ada"},
                        "created_at": f"2026-01-01T00:{i:02d}:00Z"}]}
            for i in range(1, 46)
        ]
        fake = self.patch_transport(
            {
                "/merge_requests/7": lambda url: (
                    {"iid": 7, "title": "T", "state": "opened"},
                    {},
                ),
                "/discussions": link_pages(notes, "per_page", server_max=20),
            }
        )
        target = self.mod.parse_pr_url("https://gitlab.com/g/p/-/merge_requests/7")
        brief = self.mod.fetch_gitlab_api(target)
        self.assertIn("note 45", self.mod.ending_text(brief))
        pages = fake.requested("/discussions")
        self.assertEqual(len(pages), 3)
        self.assertEqual(query_of(pages[0]).get("per_page"), "100")
        self.assertEqual(query_of(pages[2]).get("page"), "3")
        self.assertEqual(brief.notes, [])

    def test_gitea_follows_link_header_with_limit(self):
        fake = self.patch_transport(
            {
                "/pulls/7": lambda url: (
                    {"number": 7, "title": "T", "state": "open"},
                    {},
                ),
                "/issues/7/comments": link_pages(
                    numbered_comments(45), "limit", server_max=30
                ),
            }
        )
        target = self.mod.parse_pr_url("https://codeberg.org/o/r/pulls/7")
        brief = self.mod.fetch_gitea_api(target)
        self.assertIn("comment 45", self.mod.ending_text(brief))
        pages = fake.requested("/issues/7/comments")
        self.assertEqual(len(pages), 2)
        self.assertEqual(query_of(pages[0]).get("limit"), "50")
        self.assertEqual(query_of(pages[1]).get("page"), "2")

    def test_bitbucket_cloud_follows_next_field(self):
        comments = [
            {"content": {"raw": f"comment {i}"}, "user": {"display_name": "ada"},
             "created_on": f"2026-01-01T00:{i:02d}:00Z"}
            for i in range(1, 46)
        ]

        def serve(url):
            query = query_of(url)
            size = min(int(query.get("pagelen", 10)), 30)
            page = int(query.get("page", 1))
            body = {"values": comments[(page - 1) * size : page * size]}
            if page * size < len(comments):
                body["next"] = url.split("?")[0] + f"?pagelen={size}&page={page + 1}"
            return body, {}

        fake = self.patch_transport(
            {
                "/pullrequests/7": lambda url: (
                    {"id": 7, "title": "T", "state": "OPEN"},
                    {},
                ),
                "/comments": serve,
            }
        )
        target = self.mod.parse_pr_url("https://bitbucket.org/w/r/pull-requests/7")
        brief = self.mod.fetch_bitbucket_api(target)
        self.assertEqual(len(brief.comments), 45)
        self.assertIn("comment 45", self.mod.ending_text(brief))
        pages = fake.requested("/comments")
        self.assertEqual(len(pages), 2)
        self.assertEqual(query_of(pages[0]).get("pagelen"), "50")
        self.assertEqual(query_of(pages[1]).get("page"), "2")

    def test_bitbucket_server_follows_next_page_start(self):
        activities = [
            {"comment": {"text": f"comment {i}", "author": {"name": "ada"},
                         "createdDate": 1767225600000 + i * 60000}}
            for i in range(1, 46)
        ]

        def serve(url):
            query = query_of(url)
            size = min(int(query.get("limit", 25)), 30)
            start = int(query.get("start", 0))
            chunk = activities[start : start + size]
            last = start + size >= len(activities)
            body = {"values": chunk, "isLastPage": last}
            if not last:
                body["nextPageStart"] = start + size
            return body, {}

        fake = self.patch_transport(
            {
                "/pull-requests/7": lambda url: (
                    {"id": 7, "title": "T", "state": "OPEN"},
                    {},
                ),
                "/activities": serve,
            }
        )
        target = self.mod.parse_pr_url(
            "https://git.example.com/projects/KEY/repos/slug/pull-requests/7"
        )
        brief = self.mod.fetch_bitbucket_server_api(target)
        self.assertEqual(len(brief.comments), 45)
        self.assertEqual(brief.comments[-1].body, "comment 45")
        pages = fake.requested("/activities")
        self.assertEqual(len(pages), 2)
        self.assertEqual(query_of(pages[0]).get("limit"), "100")
        self.assertEqual(query_of(pages[1]).get("start"), "30")

    def test_azure_follows_continuation_token(self):
        threads = [
            {"comments": [{"content": f"comment {i}", "author": {"displayName": "ada"},
                           "publishedDate": f"2026-01-01T00:{i:02d}:00Z"}]}
            for i in range(1, 46)
        ]

        def serve(url):
            token = query_of(url).get("continuationToken")
            start = int(token or 0)
            headers = {}
            if start + 30 < len(threads):
                headers["x-ms-continuationtoken"] = str(start + 30)
            return {"value": threads[start : start + 30]}, headers

        fake = self.patch_transport(
            {
                "/pullrequests/7": lambda url: (
                    {"pullRequestId": 7, "title": "T", "status": "active"},
                    {},
                ),
                "/threads": serve,
            }
        )
        target = self.mod.parse_pr_url(
            "https://dev.azure.com/org/proj/_git/repo/pullrequest/7"
        )
        brief = self.mod.fetch_azure_api(target)
        self.assertIn("comment 45", self.mod.ending_text(brief))
        pages = fake.requested("/threads")
        self.assertEqual(len(pages), 2)
        self.assertEqual(query_of(pages[0]).get("api-version"), "7.1")
        self.assertEqual(query_of(pages[1]).get("continuationToken"), "30")
        self.assertEqual(query_of(pages[1]).get("api-version"), "7.1")

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
