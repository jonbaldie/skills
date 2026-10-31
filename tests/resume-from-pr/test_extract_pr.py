#!/usr/bin/env python3
"""Unit tests for resume-from-pr extract-pr.py (no live network)."""

from __future__ import annotations

import contextlib
import email.message
import http.client
from functools import partial
import io
import json
import socket
import struct
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from types import SimpleNamespace
from pathlib import Path
from dataclasses import asdict, FrozenInstanceError
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import load_skill_script, run_cli

load_mod = partial(load_skill_script, "resume-from-pr", "extract-pr.py")


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


REMOTE_CASES = (
    ("https://www.github.com/acme/app.git",
     ("github", "github.com", "acme", "app", None, None),
     "https://github.com/acme/app/pull/5"),
    ("git@github.com:acme/app.git",
     ("github", "github.com", "acme", "app", None, None),
     "https://github.com/acme/app/pull/5"),
    ("ssh://git@gitlab.example.com/group/sub/app.git",
     ("gitlab", "gitlab.example.com", "group/sub", "app", "group/sub/app", None),
     "https://gitlab.example.com/group/sub/app/-/merge_requests/5"),
    ("https://gitlab.com/group/sub/app.git",
     ("gitlab", "gitlab.com", "group/sub", "app", "group/sub/app", None),
     "https://gitlab.com/group/sub/app/-/merge_requests/5"),
    ("https://www.bitbucket.org/workspace/app.git",
     ("bitbucket", "bitbucket.org", "workspace", "app", None, None),
     "https://bitbucket.org/workspace/app/pull-requests/5"),
    ("git@bitbucket.org:workspace/app.git",
     ("bitbucket", "bitbucket.org", "workspace", "app", None, None),
     "https://bitbucket.org/workspace/app/pull-requests/5"),
    ("https://git.example.com/projects/KEY/repos/app.git",
     ("bitbucket-server", "git.example.com", "KEY", "app", None, None),
     "https://git.example.com/projects/KEY/repos/app/pull-requests/5"),
    ("ssh://git@git.example.com:7999/scm/KEY/app.git",
     ("bitbucket-server", "git.example.com", "KEY", "app", None, None),
     "https://git.example.com/projects/KEY/repos/app/pull-requests/5"),
    ("https://codeberg.org/acme/app.git",
     ("gitea", "codeberg.org", "acme", "app", None, None),
     "https://codeberg.org/acme/app/pulls/5"),
    ("git@git.forgejo.dev:acme/app.git",
     ("gitea", "git.forgejo.dev", "acme", "app", None, None),
     "https://git.forgejo.dev/acme/app/pulls/5"),
    ("https://org@dev.azure.com/my%20org/my%20project/_git/my%20repo",
     ("azure", "dev.azure.com", "my org", "my repo", "my project", "my org"),
     "https://dev.azure.com/my%20org/my%20project/_git/my%20repo/pullrequest/5"),
    ("https://dev.azure.com/org/_git/app",
     ("azure", "dev.azure.com", "org", "app", "org", "org"),
     "https://dev.azure.com/org/org/_git/app/pullrequest/5"),
    ("https://contoso.visualstudio.com/DefaultCollection/my%20project/_git/app",
     ("azure", "contoso.visualstudio.com", "contoso", "app", "my project", "contoso"),
     "https://dev.azure.com/contoso/my%20project/_git/app/pullrequest/5"),
    ("https://contoso.visualstudio.com/_git/app",
     ("azure", "contoso.visualstudio.com", "contoso", "app", "contoso", "contoso"),
     "https://dev.azure.com/contoso/contoso/_git/app/pullrequest/5"),
    ("git@ssh.dev.azure.com:v3/org/project/app",
     ("azure", "ssh.dev.azure.com", "org", "app", "project", "org"),
     "https://dev.azure.com/org/project/_git/app/pullrequest/5"),
    ("https://ghe.example.com/acme/app.git",
     ("unknown", "ghe.example.com", "acme", "app", None, None), None),
)


class RemoteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_numbered_remote_targets_preserve_identity_and_urls(self):
        for remote_url, identity, url in REMOTE_CASES:
            with self.subTest(remote=remote_url):
                target = self.mod.target_from_remote("5", remote_url)
                self.assertEqual(asdict(target), dict(
                    zip(("provider", "host", "owner", "repo", "project", "org"), identity),
                    number="5", url=url, original=None,
                ))
                self.assertEqual(target.slug, identity[4] or f"{identity[2]}/{identity[3]}")

    def test_remote_parsing_returns_immutable_repository_identity(self):
        for remote_url, identity, url in REMOTE_CASES:
            with self.subTest(remote=remote_url):
                repo = self.mod.repo_from_remote(remote_url)
                self.assertEqual(asdict(repo), dict(
                    zip(("provider", "host", "owner", "repo", "project", "org"), identity)
                ))
                self.assertFalse(hasattr(repo, "number"))
                self.assertFalse(hasattr(repo, "url"))
                self.assertEqual(repo.slug, identity[4] or f"{identity[2]}/{identity[3]}")
                with self.assertRaises(FrozenInstanceError):
                    repo.host = "changed.example"
                target = self.mod.target_from_repo(repo, "5")
                self.assertEqual(asdict(target), dict(
                    zip(("provider", "host", "owner", "repo", "project", "org"), identity),
                    number="5", url=url, original=None,
                ))
        self.assertIsNone(self.mod.repo_from_remote("not a remote"))
        self.assertIsNone(self.mod.repo_from_remote("https://dev.azure.com/not-a-repository"))

    def test_invalid_remote_does_not_resolve_a_target(self):
        for remote in ("not a remote", "https://dev.azure.com/not-a-repository"):
            with self.subTest(remote=remote):
                self.assertIsNone(self.mod.target_from_remote("5", remote))
        self.assertEqual(
            self.mod.target_from_remote("5", "git@github.com:acme/app.git").url,
            "https://github.com/acme/app/pull/5",
        )

    def test_bare_number_remote_precedence_and_errors(self):
        cases = (
            ([("origin", "https://unknown.example/acme/app.git"),
              ("upstream", "git@github.com:upstream/app.git")],
             ("github", "github.com", "https://github.com/upstream/app/pull/5")),
            ([("origin", "https://unknown.example/acme/app.git"),
              ("upstream", "https://other.example/team/app.git")],
             ("unknown", "unknown.example", None)),
            ([("origin", "not a remote"),
              ("upstream", "git@codeberg.org:acme/app.git")],
             ("gitea", "codeberg.org", "https://codeberg.org/acme/app/pulls/5")),
        )
        for remotes, expected in cases:
            with self.subTest(remotes=remotes), patch.object(self.mod, "git_remotes", return_value=remotes):
                target = self.mod.resolve_number("5", "workspace")
                self.assertEqual((target.provider, target.host, target.url), expected)
                self.assertEqual(target.number, "5")
        for remotes, message in (
            ([], "Number 5 needs a git remote"),
            ([("origin", "not a remote"), ("upstream", "https://other.example/acme/app.git")],
             "Could not resolve pull/merge request 5 from git remotes"),
        ):
            with self.subTest(remotes=remotes), patch.object(self.mod, "git_remotes", return_value=remotes):
                with self.assertRaisesRegex(self.mod.FetchError, message):
                    self.mod.resolve_number("5", "workspace")


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
                self.assertIn(provider.name, self.mod.PROVIDER_CREDENTIALS)
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
            credentials=(mod.Credential(("EXAMPLE_TOKEN",), "Bearer"),),
            host_pattern=r"forge\.example",
            host_precedence=5,
            url_shapes=(
                mod.UrlShape(
                    precedence=1,
                    pattern=r"^https?://(?P<host>forge\.example)/(?P<owner>[^/]+)"
                    r"/(?P<repo>[^/]+)/change/(?P<num>\d+)",
                ),
            ),
            from_remote=lambda host, path: mod.Repo(
                provider="example-forge", host=host, project=path
            ),
            target_url=lambda repo, number: (
                f"https://{repo.host}/{repo.slug}/change/{number}"
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
            repo = mod.repo_from_remote("git@forge.example:acme/app.git")
            self.assertEqual(asdict(repo), {
                "provider": "example-forge", "host": "forge.example",
                "owner": None, "repo": None, "project": "acme/app", "org": None,
            })
            t = mod.target_from_repo(repo, "4")
            self.assertEqual(t.provider, "example-forge")
            self.assertEqual(t.number, "4")
            self.assertEqual(t.url, "https://forge.example/acme/app/change/4")
            self.assertEqual(
                mod.target_from_remote("4", "git@forge.example:acme/app.git"), t
            )
        finally:
            mod.PROVIDERS = original


class LinkedIssueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()
        cls.target = cls.mod.Target("github", "github.com", "9")

    def test_closing_keyword_variants(self):
        for keyword in (
            "close", "closes", "closed", "fix", "fixes", "fixed",
            "resolve", "resolves", "resolved",
        ):
            with self.subTest(keyword=keyword):
                self.assertEqual(
                    self.mod.parse_linked_issues(f"{keyword.upper()}: #12"),
                    ["#12"],
                )

    def test_qualifies_then_deduplicates_in_encounter_order(self):
        self.assertEqual(
            self.mod.parse_linked_issues(
                "Closes #12. Fixes other/repo#34. Resolved acme/app#12. "
                "Closed #56. Fixes other/repo#34.",
                default_repo="acme/app",
            ),
            ["acme/app#12", "other/repo#34", "acme/app#56"],
        )

    def test_empty_text_and_non_closing_mentions(self):
        for text in ("", "See #12 and other/repo#34. Fix the bug in #56."):
            with self.subTest(text=text):
                self.assertEqual(self.mod.parse_linked_issues(text), [])
        self.assertEqual(
            self.mod.parse_linked_issues("Closes #12. See #34. Fixes #12."),
            ["#12"],
        )

    def test_native_github_references_keep_titles_without_parsed_duplicates(self):
        brief = self.mod.brief_from_github_view({
            "body": "Closes #12. Fixes other/repo#34.",
            "closingIssuesReferences": [
                {"number": 12, "title": "Local issue"},
                {"number": 34, "title": "Remote issue",
                 "repository": {"nameWithOwner": "other/repo"}},
            ],
        }, target=self.target)
        self.assertEqual(brief.linked_issues, ["#12 Local issue", "other/repo#34 Remote issue"])
        self.assertIn(
            "## Linked issues\n- #12 Local issue\n- other/repo#34 Remote issue\n",
            self.mod.render(brief),
        )

    def test_github_falls_back_when_native_references_are_empty(self):
        for native in (None, []):
            with self.subTest(native=native):
                brief = self.mod.brief_from_github_view({
                    "body": "Closes #12. Fixes #12.",
                    "closingIssuesReferences": native,
                }, target=self.target)
                self.assertEqual(brief.linked_issues, ["#12"])

    def test_provider_descriptions_render_linked_issues(self):
        mod = self.mod
        body = "Closes #12. Fixes other/repo#34. Closes #12."
        briefs = [
            ("github-cli", mod.brief_from_github_view({"body": body}, target=self.target), "#12"),
            ("github-rest", mod.brief_from_github_rest({"body": body}, target=self.target), "#12"),
            ("gitlab", mod.brief_from_gitlab({
                "description": body, "web_url": "https://gitlab.com/acme/app/-/merge_requests/7",
            }), "acme/app#12"),
            ("bitbucket", mod.brief_from_bitbucket({
                "description": body,
                "destination": {"repository": {"full_name": "acme/app"}},
            }), "acme/app#12"),
            ("azure", mod.brief_from_azure({
                "description": body, "repository": {"name": "app"},
            }), "app#12"),
            ("git", mod.brief_from_git(
                mod.Target(provider="github", host="github.com", number="7", owner="acme", repo="app"),
                sha="abc1234", ref="refs/pull/7/head", remote_url="origin", message=body,
            ), "acme/app#12"),
        ]
        for provider, brief, local in briefs:
            with self.subTest(provider=provider):
                self.assertEqual(brief.linked_issues, [local, "other/repo#34"])
                self.assertIn(
                    f"## Linked issues\n- {local}\n- other/repo#34\n",
                    mod.render(brief),
                )

    def test_missing_repository_keeps_references_unqualified(self):
        for normalize in (
            self.mod.brief_from_gitlab,
            self.mod.brief_from_bitbucket,
            self.mod.brief_from_azure,
        ):
            with self.subTest(provider=normalize.__name__):
                brief = normalize({"description": "Closes #12."})
                self.assertEqual(brief.linked_issues, ["#12"])


class BriefRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()
        cls.target = cls.mod.Target("github", "github.com", "9")

    def test_gitea_rest_uses_resolved_target_identity(self):
        target = self.mod.Target(
            provider="gitea", host="codeberg.org", number="9", owner="acme", repo="app"
        )
        for url in (None, "https://github.com/wrong/project/pull/9"):
            with self.subTest(url=url):
                pr = {"number": 9, "title": "Fix auth", "state": "open", "html_url": url}
                brief = self.mod.brief_from_github_rest(pr, target=target)
                text = self.mod.render(brief)
                self.assertIn("provider: gitea\n", text)
                self.assertIn("host: codeberg.org\n", text)
                self.assertIn("repo: acme/app\n", text)

    def test_gitlab_glab_renders_embedded_discussions_like_api(self):
        target = self.mod.Target(
            provider="gitlab", host="gitlab.com", number="7", project="group/app"
        )
        mr = {"iid": 7, "title": "Add cache", "state": "opened"}
        discussions = [{"notes": [
            {"body": "Watch the TTL.", "author": {"username": "reviewer"},
             "created_at": "2024-01-02T03:04:05Z"},
            {"body": "Check this line.", "author": {"username": "ada"},
             "position": {"new_path": "cache.py", "new_line": 12}},
            {"body": "changed the title", "system": True},
        ]}]
        with patch.object(self.mod, "run_cmd", return_value=json.dumps(dict(mr, discussions=discussions))):
            cli = self.mod.fetch_gitlab_glab(target)
        api = self.mod.brief_from_gitlab(mr, discussions=discussions, host=target.host)
        self.assertEqual([asdict(comment) for comment in cli.comments], [
            asdict(comment) for comment in api.comments
        ])
        text = self.mod.render(cli)
        self.assertIn("### Comment — reviewer\nWatch the TTL.", text)
        self.assertIn("### cache.py:12 — ada\nCheck this line.", text)
        self.assertNotIn("changed the title", text)

    def test_gitlab_main_renders_glab_v126_discussions(self):
        payload = {
            "iid": 7, "title": "Add cache", "state": "opened",
            "Discussions": [{"id": "abc", "individual_note": False, "notes": [
                {"body": "Watch the TTL.", "author": {"username": "reviewer"},
                 "created_at": "2024-01-02T03:04:05Z", "system": False, "position": None},
                {"body": "Check this line.", "author": {"username": "ada"}, "system": False,
                 "position": {"new_path": "cache.py", "new_line": 12}},
                {"body": "changed the title", "system": True},
            ]}],
        }
        output = io.StringIO()
        with patch.object(self.mod, "run_cmd", return_value=json.dumps(payload)):
            with contextlib.redirect_stdout(output):
                self.assertEqual(self.mod.main(["https://gitlab.com/group/app/-/merge_requests/7"]), 0)
        text = output.getvalue()
        self.assertIn("### Comment — reviewer\nWatch the TTL.", text)
        self.assertIn("### cache.py:12 — ada\nCheck this line.", text)
        self.assertNotIn("changed the title", text)

    def test_gitlab_explicit_empty_discussions_override_payload(self):
        mr = {"discussions": [{"notes": [{"body": "Embedded comment"}]}]}
        embedded = self.mod.brief_from_gitlab(mr)
        explicit = self.mod.brief_from_gitlab(mr, discussions=[])
        api = self.mod.brief_from_gitlab(
            mr, discussions=[{"notes": [{"body": "API comment"}]}]
        )
        self.assertEqual([comment.body for comment in embedded.comments], ["Embedded comment"])
        self.assertEqual(explicit.comments, [])
        self.assertEqual([comment.body for comment in api.comments], ["API comment"])

    def test_bitbucket_server_normalizes_payload_without_http(self):
        target = self.mod.Target(
            provider="bitbucket-server", host="git.example.com", number="4",
            owner="KEY", repo="slug",
            url="https://git.example.com/projects/KEY/repos/slug/pull-requests/4",
        )
        pr = {
            "id": 4, "title": "Fix cache", "state": "OPEN", "draft": True,
            "author": {"user": {"name": "ada"}}, "description": "Fixes #12.",
            "fromRef": {"displayId": "feature/cache", "latestCommit": "abc123"},
            "toRef": {"displayId": "main"},
        }
        changes = [{"path": {"toString": "cache.py"}, "type": "MODIFY"}]
        activities = [{"comment": {
            "text": "Watch the TTL.", "author": {"name": "reviewer"},
            "createdDate": 1704164645000,
        }}]
        brief = self.mod.brief_from_bitbucket_server(pr, changes, activities, target=target)
        self.assertEqual(
            (brief.provider, brief.host, brief.repo, brief.url, brief.number, brief.source),
            ("bitbucket-server", "git.example.com", "KEY/slug", target.url, "4", "api"),
        )
        self.assertEqual(
            (brief.title, brief.state, brief.author, brief.body, brief.draft,
             brief.base, brief.head, brief.head_sha, brief.linked_issues),
            ("Fix cache", "open", "ada", "Fixes #12.", True,
             "main", "feature/cache", "abc123", ["KEY/slug#12"]),
        )
        self.assertEqual([(f.path, f.change_type) for f in brief.files], [("cache.py", "MODIFY")])
        self.assertEqual(
            [(c.author, c.body, c.created, c.kind) for c in brief.comments],
            [("reviewer", "Watch the TTL.", "2024-01-02T03:04:05+00:00", "discussion")],
        )
        text = self.mod.render(brief)
        self.assertIn("- cache.py MODIFY", text)
        self.assertIn("### Comment — reviewer\nWatch the TTL.", text)

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
        brief = self.mod.brief_from_github_view(
            data, inline=inline, source="gh",
            target=self.mod.Target("github", "github.com", "9", owner="acme", repo="app"),
        )
        text = self.mod.render(brief)
        self.assertIn("provider: github", text)
        self.assertIn("number: 9", text)
        self.assertIn("repo: acme/app\n", text)
        self.assertIn("host: github.com\n", text)
        self.assertIn("draft: true", text)
        self.assertIn("src/auth.ts (+10/-2)", text)
        self.assertIn("## Goal", text)
        self.assertIn("Continue the interceptor work.", text)
        self.assertIn("src/auth.ts:44 — linus", text)
        self.assertIn("This leaks the token.", text)
        self.assertIn("tests: failure", text)
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
        self.assertIn("pipeline: failure", text)

    def test_gitlab_brief_repo_is_project_path(self):
        # GitLab's references.full names the merge request, not the project.
        mr = {
            "iid": 4044,
            "web_url": "https://gitlab.com/gitlab-org/cli/-/merge_requests/4044",
            "references": {"short": "!4044", "full": "gitlab-org/cli!4044"},
        }
        brief = self.mod.brief_from_gitlab(mr, host="gitlab.com")
        self.assertIn("repo: gitlab-org/cli\n", self.mod.render(brief))

    def test_gitlab_brief_repo_from_web_url(self):
        mr = {
            "iid": 7,
            "web_url": "https://gitlab.com/group/sub/app/-/merge_requests/7",
        }
        brief = self.mod.brief_from_gitlab(mr, host="gitlab.com")
        self.assertEqual(brief.repo, "group/sub/app")

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
        brief = self.mod.brief_from_github_view(data, target=self.target)
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
            target=self.target,
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
            }, target=self.target
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


class ReviewStatePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()
        cls.target = cls.mod.Target("github", "github.com", "9")

    def test_github_normalizers_separate_state_and_preserve_review_text(self):
        briefs = [
            self.mod.brief_from_github_view({
                "reviewDecision": "CHANGES_REQUESTED",
                "reviews": [{"state": "CHANGES_REQUESTED", "body": "  Add a test.  ",
                             "author": {"login": "reviewer"}}],
            }, target=self.target),
            self.mod.brief_from_github_rest(
                {"reviewDecision": "CHANGES_REQUESTED"}, target=self.target,
                reviews=[{"state": "changes_requested", "body": "  Add a test.  ",
                          "user": {"login": "reviewer"}}],
            ),
        ]
        for brief, state in zip(briefs, ("CHANGES_REQUESTED", "changes_requested")):
            with self.subTest(source=brief.source):
                review = brief.comments[0]
                self.assertEqual(review.body, "Add a test.")
                self.assertEqual(review.state, state)
                text = self.mod.render(brief)
                self.assertIn(f"### Review — reviewer\n{state}\nAdd a test.\n", text)
                self.assertEqual(
                    self.mod.ending_text(brief),
                    f"Changes Requested. reviewer: {state}\nAdd a test.",
                )

    def test_review_prose_does_not_supply_a_verdict(self):
        for state in ("COMMENTED", "APPROVED", None):
            with self.subTest(state=state):
                brief = self.mod.brief_from_github_view({
                    "reviewDecision": "CHANGES_REQUESTED",
                    "reviews": [{"state": state, "body": "Document CHANGES_REQUESTED.",
                                 "author": {"login": "reviewer"}}],
                }, target=self.target)
                self.assertEqual(self.mod.ending_text(brief), "Changes Requested")
                self.assertIn("Document CHANGES_REQUESTED.", self.mod.render(brief))

    def test_provider_independent_state_supplies_review_context(self):
        brief = self.mod.Brief(
            provider="example", url="https://example.com/pull/1", number="1",
            title="T", state="open", author="ada", review_decision="CHANGES_REQUESTED",
            comments=[self.mod.Comment(author="reviewer", body="Add a test.",
                                       kind="review", state="changes_requested")],
        )
        self.assertEqual(
            self.mod.ending_text(brief),
            "Changes Requested. reviewer: changes_requested\nAdd a test.",
        )
        self.assertIn(
            "### Review — reviewer\nchanges_requested\nAdd a test.\n",
            self.mod.render(brief),
        )

    def test_state_only_reviews_remain_visible_and_supply_the_ending(self):
        brief = self.mod.brief_from_github_view({
            "reviews": [
                {"state": "APPROVED", "body": "  ", "author": {"login": "reviewer"}},
                {"body": "  ", "author": {"login": "empty"}},
            ],
        }, target=self.target)
        self.assertEqual([(c.body, c.state) for c in brief.comments], [("", "APPROVED")])
        self.assertIn("### Review — reviewer\nAPPROVED\n", self.mod.render(brief))
        self.assertEqual(self.mod.ending_text(brief), "reviewer: APPROVED")
        brief.review_decision = "APPROVED"
        self.assertEqual(self.mod.ending_text(brief), "Approved")

    def test_empty_changes_request_body_still_supplies_context(self):
        brief = self.mod.brief_from_github_view({
            "reviewDecision": "CHANGES_REQUESTED",
            "reviews": [{"state": "CHANGES_REQUESTED", "body": "",
                         "author": {"login": "reviewer"}}],
        }, target=self.target)
        self.assertEqual(brief.comments[0].body, "")
        self.assertEqual(
            self.mod.ending_text(brief), "Changes Requested. reviewer: CHANGES_REQUESTED"
        )

    def test_review_truncation_includes_state_in_the_existing_limits(self):
        brief = self.mod.brief_from_github_view({
            "reviews": [{"state": "CHANGES_REQUESTED", "body": "x" * 1600,
                         "author": {"login": "reviewer"}}],
        }, target=self.target)
        text = self.mod.render(brief)
        self.assertIn(
            "### Review — reviewer\nCHANGES_REQUESTED\n" + "x" * 1481 + "…\n", text
        )
        self.assertEqual(
            self.mod.ending_text(brief), "reviewer: CHANGES_REQUESTED\n" + "x" * 771 + "…"
        )
        brief.review_decision = "CHANGES_REQUESTED"
        self.assertEqual(
            self.mod.ending_text(brief),
            "Changes Requested. reviewer: CHANGES_REQUESTED\n" + "x" * 752 + "…",
        )

    def test_providers_without_verdicts_keep_comment_kinds_and_text(self):
        briefs = [
            self.mod.brief_from_gitlab({}, discussions=[{"notes": [
                {"body": "Discuss.", "author": {"username": "ada"}},
                {"body": "Inline.", "position": {"new_path": "a.py", "new_line": 1}},
            ]}]),
            self.mod.brief_from_bitbucket({}, comments=[
                {"content": {"raw": "Discuss."}, "user": {"display_name": "ada"}},
                {"content": {"raw": "Inline."}, "inline": {"path": "a.py", "to": 1}},
            ]),
            self.mod.brief_from_azure({}, threads=[
                {"comments": [{"content": "Discuss.", "author": {"displayName": "ada"}}]},
                {"threadContext": {"filePath": "/a.py"},
                 "comments": [{"content": "Inline."}]},
            ]),
        ]
        for brief in briefs:
            with self.subTest(provider=brief.provider):
                self.assertEqual(
                    [(c.kind, c.body, c.state) for c in brief.comments],
                    [("discussion", "Discuss.", None), ("inline", "Inline.", None)],
                )
                self.assertIn("### Comment — ada\nDiscuss.\n", self.mod.render(brief))
                self.assertEqual(self.mod.ending_text(brief), "ada: Discuss.")

    def test_normalized_check_failures_drive_rendered_ending(self):
        for raw, canonical in (
            ("TIMED_OUT", "failure"), ("partiallySucceeded", "failure"),
            ("STOPPED", "canceled"), ("ERROR", "error"),
            ("actionRequired", "action_required"),
        ):
            with self.subTest(status=raw):
                brief = self.mod.brief_from_github_view({
                    "comments": [{"body": "Continue.", "author": {"login": "ada"}}],
                    "statusCheckRollup": [{"name": "ci", "conclusion": raw}],
                }, target=self.target)
                self.assertEqual(brief.checks[0].status, canonical)
                self.assertIn(f"- ci: {canonical}\n", self.mod.render(brief))
                self.assertIn("## Ending\nFailing checks: ci\n", self.mod.render(brief))
        brief = self.mod.brief_from_github_view({
            "comments": [{"body": "Continue.", "author": {"login": "ada"}}],
            "statusCheckRollup": [{"name": "ci", "conclusion": "SUCCESS"}],
        }, target=self.target)
        self.assertIn("## Ending\nada: Continue.\n", self.mod.render(brief))


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

    def test_current_branch_lookups_receive_repository_identity(self):
        cases = (
            ("git@github.com:acme/app.git", "github",
             "https://api.github.com/repos/acme/app/pulls",
             [{"number": 42, "html_url": "https://github.com/acme/app/pull/42"}],
             "https://github.com/acme/app/pull/42"),
            ("git@gitlab.com:acme/app.git", "gitlab",
             "https://gitlab.com/api/v4/projects/acme%2Fapp/merge_requests",
             [{"iid": 42, "web_url": "https://gitlab.com/acme/app/-/merge_requests/42"}],
             "https://gitlab.com/acme/app/-/merge_requests/42"),
            ("git@bitbucket.org:acme/app.git", "bitbucket",
             "https://api.bitbucket.org/2.0/repositories/acme/app/pullrequests",
             {"values": [{"id": 42, "links": {"html": {"href": "https://bitbucket.org/acme/app/pull-requests/42"}}}]},
             "https://bitbucket.org/acme/app/pull-requests/42"),
            ("https://git.example.com/scm/KEY/app.git", "bitbucket-server",
             "https://git.example.com/rest/api/1.0/projects/KEY/repos/app/pull-requests",
             {"values": [{"id": 42}]},
             "https://git.example.com/projects/KEY/repos/app/pull-requests/42"),
            ("git@codeberg.org:acme/app.git", "gitea",
             "https://codeberg.org/api/v1/repos/acme/app/pulls",
             [{"number": 42, "html_url": "https://codeberg.org/acme/app/pulls/42",
               "head": {"ref": "feature/x", "repo": {"full_name": "acme/app"}}}],
             "https://codeberg.org/acme/app/pulls/42"),
            ("git@ssh.dev.azure.com:v3/org/project/app", "azure",
             "https://dev.azure.com/org/project/_apis/git/repositories/app/pullrequests",
             {"value": [{"pullRequestId": 42}]},
             "https://dev.azure.com/org/project/_git/app/pullrequest/42"),
        )
        for remote_url, provider, api_root, response, expected_url in cases:
            with self.subTest(provider=provider):
                self.patch_run_cmd(f"origin\t{remote_url} (fetch)\n", branch="feature/x")
                forge = FakeForge(self, self.mod)
                forge.route(api_root, single(response))
                lookup = self.mod.BRANCH_LOOKUPS[provider]
                received = []

                def checked_lookup(repo, branch):
                    self.assertIsInstance(repo, self.mod.Repo)
                    self.assertFalse(hasattr(repo, "number"))
                    self.assertFalse(hasattr(repo, "url"))
                    received.append((repo.provider, repo.slug, branch))
                    return lookup(repo, branch)

                with patch.dict(self.mod.BRANCH_LOOKUPS, {provider: checked_lookup}):
                    target = self.mod.resolve_current_branch("workspace")
                self.assertEqual(target.number, "42")
                self.assertEqual(target.url, expected_url)
                expected_slug = "project" if provider == "azure" else (
                    "KEY/app" if provider == "bitbucket-server" else "acme/app"
                )
                self.assertEqual(received, [(provider, expected_slug, "feature/x")])

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
        FakeForge(self, self.mod).route(
            "https://codeberg.org/api/v1/repos/owner/repo/pulls",
            single(
                [
                    {
                        "number": 9,
                        "html_url": "https://codeberg.org/owner/repo/pulls/9",
                        "head": {"ref": "feature/x", "repo": {"full_name": "owner/repo"}},
                    }
                ]
            ),
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



class FakeForge(urllib.request.BaseHandler):
    """Offline HTTP transport; retain the real opener and redirect machinery."""

    handler_order = 100  # before urllib's network HTTP(S) handlers

    def __init__(self, testcase, mod):
        self.mod = mod
        self.routes = {}
        self.requests = []
        self.request_objects = []
        original = mod.urllib.request.build_opener
        mod.urllib.request.build_opener = lambda *handlers: original(*handlers, self)
        testcase.addCleanup(setattr, mod.urllib.request, "build_opener", original)

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
        self.request_objects.append(request)
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
        body, headers = result[:2]
        code = result[2] if len(result) > 2 else 200
        message = email.message.Message()
        for key, value in headers.items():
            message[key] = value
        response = urllib.response.addinfourl(
            io.BytesIO(json.dumps(body).encode()), message, url, code
        )
        response.msg = "fixture"
        return response

    http_open = urlopen
    https_open = urlopen


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


class ForgeReaderScopeTests(unittest.TestCase):
    """Observe real Requests at an offline opener's HTTP(S) transport boundary."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def setUp(self):
        self.forge = FakeForge(self, self.mod)
        self.url = "https://forge.invalid/api/items"
        self.headers = {
            "Authorization": "Bearer SYNTHETIC",
            "Private-token": "SYNTHETIC",
        }
        self.reader = self.mod.ForgeReader(self.url, self.headers)

    def assert_credentials(self, request):
        headers = {k.lower(): v for k, v in request.header_items()}
        for key, value in self.headers.items():
            self.assertEqual(headers[key.lower()], value)

    def test_normal_reads_and_default_ports_keep_credentials(self):
        for trusted, destination in (
            (self.url, self.url),
            (self.url, "https://forge.invalid:443/api/items"),
            ("https://forge.invalid:443/api/items", self.url),
            ("http://forge.invalid/api/items", "http://forge.invalid:80/api/items"),
        ):
            with self.subTest(trusted=trusted, destination=destination):
                self.forge.route(destination, single({"ok": True}))
                reader = self.mod.ForgeReader(trusted, self.headers)
                self.assertEqual(reader.json(destination), {"ok": True})
                self.assert_credentials(self.forge.request_objects[-1])

    def test_unsafe_reads_are_rejected_before_request_construction(self):
        original = self.mod.urllib.request.Request
        constructed = []

        def record(*args, **kwargs):
            constructed.append(args[0])
            return original(*args, **kwargs)

        self.mod.urllib.request.Request = record
        self.addCleanup(setattr, self.mod.urllib.request, "Request", original)
        for url in (
            "https://outside.invalid/next", "//outside.invalid/next",
            "https://forge.invalid:444/next", "http://forge.invalid/next",
            "https://user:pass@forge.invalid/next", "file:///tmp/next",
            "https://forge.invalid:bad/next", "https://[invalid/next",
        ):
            with self.subTest(url=url):
                with self.assertRaises(self.mod.FetchError):
                    self.reader.json(url)
        self.assertEqual(constructed, [])
        self.assertEqual(self.forge.request_objects, [])

    def test_both_paging_policies_reject_origin_changes(self):
        for paging in (self.mod.GITHUB_PAGING, self.mod.BITBUCKET_PAGING):
            for link in ("https://outside.invalid/next", "https://forge.invalid:444/next",
                         "http://forge.invalid/next"):
                with self.subTest(paging=paging, link=link):
                    self.forge.request_objects.clear()
                    body = [1] if paging.items is None else {"values": [1], "next": link}
                    headers = {"Link": f'<{link}>; rel="next"'}
                    self.forge.route(self.url, lambda key, query: (body, headers))
                    result = self.mod.http_collection(self.url, self.reader, paging, "items")
                    self.assertEqual(result.items, [1])
                    self.assertIn("unsafe", result.note)
                    self.assertEqual(len(self.forge.request_objects), 1)
                    self.assert_credentials(self.forge.request_objects[0])

    def test_relative_pagination_keeps_credentials(self):
        for paging in (self.mod.GITHUB_PAGING, self.mod.BITBUCKET_PAGING):
            with self.subTest(paging=paging):
                self.forge.request_objects.clear()
                first = [1] if paging.items is None else {"values": [1], "next": "?page=2"}
                last = [2] if paging.items is None else {"values": [2]}
                self.forge.route(self.url, lambda key, query: (
                    (last, {}) if query.get("page") == "2" else
                    (first, {"Link": '<?page=2>; rel="next"'})
                ))
                result = self.mod.http_collection(self.url, self.reader, paging, "items")
                self.assertEqual(result.items, [1, 2])
                self.assertIsNone(result.note)
                self.assertEqual(len(self.forge.request_objects), 2)
                for request in self.forge.request_objects:
                    self.assert_credentials(request)

    def test_redirect_origin_changes_never_reach_transport(self):
        for code in (301, 302, 303, 307, 308):
            for destination in ("https://outside.invalid/next", "//outside.invalid/next",
                                "https://forge.invalid:444/next", "http://forge.invalid/next"):
                with self.subTest(code=code, destination=destination):
                    self.forge.request_objects.clear()
                    self.forge.route(self.url, lambda key, query: (
                        {}, {"Location": destination}, code
                    ))
                    with self.assertRaisesRegex(self.mod.FetchError, "unsafe"):
                        self.reader.json(self.url)
                    self.assertEqual(len(self.forge.request_objects), 1)
                    self.assert_credentials(self.forge.request_objects[0])

    def test_same_origin_redirects_and_relative_followups_remain_usable(self):
        for destination in ("/moved/items", "https://forge.invalid:443/moved/items"):
            with self.subTest(destination=destination):
                self.forge.request_objects.clear()
                self.forge.route(self.url, lambda key, query: (
                    {}, {"Location": destination}, 302
                ))
                moved = urllib.parse.urljoin(self.url, destination)
                self.forge.route(moved, single({"values": [1], "next": "next"}))
                self.forge.route(urllib.parse.urljoin(moved, "next"), single({"values": [2]}))
                result = self.mod.http_collection(
                    self.url, self.reader, self.mod.BITBUCKET_PAGING, "items"
                )
                self.assertEqual(result.items, [1, 2])
                self.assertIsNone(result.note)
                self.assertEqual(len(self.forge.request_objects), 3)
                for request in self.forge.request_objects:
                    self.assert_credentials(request)


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

    def test_unsafe_link_pagination_preserves_items_and_renders_gap(self):
        target = self.github_forge(comments=[])
        url = "https://api.github.com/repos/acme/app/issues/9/comments"
        self.forge.route(url, lambda key, query: (
            self.numbered_comments(1),
            {"Link": '<https://outside.invalid/next>; rel="next"'},
        ))
        self.enterContext(patch.dict(self.mod.os.environ, {"GH_TOKEN": "SYNTHETIC"}, clear=True))
        brief = self.mod.fetch_github_api(target)
        self.assertEqual([c.body for c in brief.comments], ["comment 1"])
        outside = [r for r in self.forge.request_objects if "outside.invalid" in r.full_url]
        self.assertEqual(outside, [], "untrusted request reached transport with credentials")
        self.assertIn("## Gaps", self.mod.render(brief))
        self.assertIn("unsafe", self.mod.render(brief).lower())

    def test_unsafe_body_pagination_never_reaches_transport(self):
        url = "https://api.bitbucket.org/2.0/items"
        self.forge.route(url, single({"values": [1], "next": "https://outside.invalid/next"}))
        reader = self.mod.ForgeReader(url, {"Authorization": "Bearer SYNTHETIC"})
        result = self.mod.http_collection(url, reader, self.mod.BITBUCKET_PAGING, "comments")
        self.assertEqual(result.items, [1])
        self.assertEqual(len(self.forge.request_objects), 1,
                         "untrusted request reached transport with credentials")
        self.assertIn("unsafe", result.note.lower())

    def test_github_cli_uses_review_state_not_a_newer_prose_mention(self):
        target = self.github_forge(comments=[], reviews=link_pager([
            {"state": "changes_requested", "body": "Add a test.",
             "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T11:00:00Z"},
            {"state": "commented", "body": "Document CHANGES_REQUESTED.",
             "user": {"login": "ada"}, "submitted_at": "2026-01-01T12:00:00Z"},
        ], "per_page", 30, 30))
        self.forge.route("https://api.github.com/repos/acme/app/pulls/9", single({
            "number": 9, "title": "T", "state": "open", "html_url": target.url,
            "head": {"sha": "abc1234"}, "reviewDecision": "CHANGES_REQUESTED",
        }))
        self.enterContext(patch.dict(self.mod.os.environ, {"GH_TOKEN": "SYNTHETIC"}, clear=True))
        self.enterContext(patch.object(self.mod, "run_cmd", side_effect=self.mod.Skip("offline")))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.mod.main([target.url]), 0)
        self.assertIn(
            "### Review — ada\ncommented\nDocument CHANGES_REQUESTED.\n", output.getvalue()
        )
        self.assertIn(
            "## Ending\nChanges Requested. reviewer: changes_requested\nAdd a test.\n",
            output.getvalue(),
        )

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
            "- build (ubuntu-latest): failure\n"
            "- build (windows-latest): failure\n"
            "- build (macos-latest): failure\n"
            "- lint: pending\n",
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

    def test_gh_dispatch_recovers_identity_from_successful_url(self):
        remote = self.mod.repo_from_remote("git@example.com:acme/app.git")
        cases = [
            (self.mod.target_from_repo(remote, "9"), "example.com"),
            (self.mod.Target("github", "", "9"), "github.com"),
            (self.mod.Target("github", "", "9", owner="partial"), "github.com"),
        ]
        payload = json.dumps({"number": 9, "url": "https://github.com/acme/app/pull/9"})
        for target, host in cases:
            with self.subTest(target=target):
                with patch.object(self.mod, "run_cmd", return_value=payload):
                    brief = self.mod.fetch_brief(target, None)
                self.assertEqual(
                    (brief.provider, brief.host, brief.repo),
                    ("github", host, "acme/app"),
                )
                self.assertIn("provider: github\n", self.mod.render(brief))

    def test_unknown_dispatch_identifies_successful_github_api(self):
        target = self.github_forge(comments=[])
        target.provider = "unknown"
        with patch.object(self.mod, "run_cmd", side_effect=self.mod.Skip("gh unavailable")):
            brief = self.mod.fetch_brief(target, None)
        self.assertEqual((brief.provider, brief.host, brief.repo),
                         ("github", "github.com", "acme/app"))

    def test_gitea_dispatch_keeps_complete_target_over_payload_url(self):
        root = "https://codeberg.org/api/v1/repos/owner/repo/pulls/9"
        self.forge.route(root, single({
            "number": 9, "html_url": "https://github.com/wrong/project/pull/9",
        }))
        for path in ("files", "reviews"):
            self.forge.route(f"{root}/{path}", link_pager([], "limit", 30, 1))
        self.forge.route(
            "https://codeberg.org/api/v1/repos/owner/repo/issues/9/comments",
            link_pager([], "limit", 30, 1),
        )
        target = self.mod.parse_pr_url("https://codeberg.org/owner/repo/pulls/9")
        brief = self.mod.fetch_brief(target, None)
        self.assertEqual(
            (brief.provider, brief.host, brief.repo),
            ("gitea", "codeberg.org", "owner/repo"),
        )

    def test_gitea_api_brief_names_the_gitea_provider(self):
        root = "https://gitea.com/api/v1/repos/gitea/tea/pulls/1126"
        self.forge.route(
            root,
            single({
                "number": 1126, "title": "PR", "state": "open", "user": {"login": "ada"},
                "body": "Closes #12. Fixes other/repo#34.",
            }),
        )
        for path in ("files", "reviews"):
            self.forge.route(f"{root}/{path}", link_pager([], "limit", 30, 1))
        self.forge.route(
            "https://gitea.com/api/v1/repos/gitea/tea/issues/1126/comments",
            link_pager([], "limit", 30, 1),
        )
        target = self.mod.parse_pr_url("https://gitea.com/gitea/tea/pulls/1126")
        text = self.mod.render(self.mod.fetch_gitea_api(target))
        self.assertIn("provider: gitea\n", text)
        self.assertIn("host: gitea.com\n", text)
        self.assertIn("## Linked issues\n- #12\n- other/repo#34\n", text)

    def gitea_open_prs(self, prs, fail_page=None):
        pulls = "https://codeberg.org/api/v1/repos/owner/repo/pulls"
        pager = link_pager(prs, "limit", 30, 2)

        def handler(key, query):
            if fail_page and query.get("page") == str(fail_page):
                return 500
            return pager(key, query)

        self.forge.route(pulls, handler)
        remote = self.mod.repo_from_remote("https://codeberg.org/owner/repo.git")
        return pulls, remote

    @staticmethod
    def gitea_pr(number, ref, full_name="owner/repo"):
        return {
            "number": number,
            "html_url": f"https://codeberg.org/{full_name}/pulls/{number}",
            "head": {"ref": ref, "repo": {"full_name": full_name}},
        }

    def test_gitea_branch_lookup_reads_past_first_page(self):
        prs = [self.gitea_pr(n, f"other-{n}") for n in range(1, 3)]
        prs.append(self.gitea_pr(30, "feature/x"))
        pulls, remote = self.gitea_open_prs(prs)
        t = self.mod.gitea_branch_target(remote, "feature/x")
        self.assertEqual(t.number, "30")
        pages = self.forge.requested(pulls)
        self.assertEqual([p.get("page") for p in pages], [None, "2"])
        self.assertEqual({p.get("state") for p in pages}, {"open"})

    def test_gitea_branch_lookup_prefers_same_repo_on_later_page(self):
        prs = [
            self.gitea_pr(5, "feature/x", full_name="fork/repo"),
            self.gitea_pr(6, "other"),
            self.gitea_pr(7, "feature/x"),
        ]
        _, remote = self.gitea_open_prs(prs)
        t = self.mod.gitea_branch_target(remote, "feature/x")
        self.assertEqual(t.number, "7")

    def test_gitea_branch_lookup_complete_listing_without_match(self):
        prs = [self.gitea_pr(n, f"other-{n}") for n in range(1, 4)]
        _, remote = self.gitea_open_prs(prs)
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.gitea_branch_target(remote, "feature/x")
        self.assertIn("no open pull request for branch 'feature/x'", str(ctx.exception))

    def test_gitea_branch_lookup_incomplete_listing_without_match(self):
        prs = [self.gitea_pr(n, f"other-{n}") for n in range(1, 4)]
        prs.append(self.gitea_pr(30, "feature/x"))
        _, remote = self.gitea_open_prs(prs, fail_page=2)
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.gitea_branch_target(remote, "feature/x")
        message = str(ctx.exception)
        self.assertNotIn("no open pull request", message)
        self.assertIn("incomplete", message)
        self.assertIn("HTTP 500", message)

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
            single({
                "id": 4, "title": "PR", "state": "OPEN", "author": {"user": {"name": "ada"}},
                "description": "Closes #12. Fixes other/repo#34.",
            }),
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
        self.assertEqual(brief.linked_issues, ["KEY/slug#12", "other/repo#34"])
        self.assertIn(
            "## Linked issues\n- KEY/slug#12\n- other/repo#34\n",
            self.mod.render(brief),
        )
        self.assertEqual(len(brief.files), 5)
        self.assertEqual(len(brief.comments), 5)
        pages = self.forge.requested(f"{root}/activities")
        self.assertEqual([p.get("limit") for p in pages], ["100"] * 3)
        self.assertEqual([p.get("start") for p in pages], [None, "2", "4"])
        self.assertEqual(brief.notes, [])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.mod.main([target.url]), 0)
        self.assertIn(
            "## Linked issues\n- KEY/slug#12\n- other/repo#34\n",
            output.getvalue(),
        )

    def test_bitbucket_server_epoch_dates_order_with_iso_events_and_cli(self):
        root = "https://git.example.com/rest/api/1.0/projects/KEY/repos/slug/pull-requests/4"
        self.forge.route(root, single({"id": 4, "title": "PR", "state": "OPEN"}))
        self.forge.route(f"{root}/changes", bitbucket_server_pager([], 2))
        self.forge.route(f"{root}/activities", bitbucket_server_pager([
            {"createdDate": 1767268800123,
             "comment": {"text": "Latest.", "author": {"name": "ada"}}},
            {"comment": {"text": "Earlier.", "author": {"name": "ada"},
                         "createdDate": "1767265200000"}},
            {"comment": {"text": "Epoch.", "author": {"name": "ada"}, "createdDate": 0}},
        ], 2))
        target = self.mod.parse_pr_url(
            "https://git.example.com/projects/KEY/repos/slug/pull-requests/4"
        )
        self.enterContext(patch.dict(self.mod.os.environ, {"BITBUCKET_TOKEN": "SYNTHETIC"}, clear=True))
        brief = self.mod.fetch_bitbucket_server_api(target)
        self.assertEqual([c.created for c in brief.comments], [
            "2026-01-01T12:00:00.123000+00:00", "2026-01-01T11:00:00+00:00",
            "1970-01-01T00:00:00+00:00",
        ])
        self.assertEqual([(c.kind, c.state) for c in brief.comments], [("discussion", None)] * 3)
        brief.comments.append(self.mod.Comment(
            author="linus", body="ISO event.", created="2026-01-01T11:30:00Z"
        ))
        self.assertEqual(
            [c.body for c in self.mod.chronological_events(brief.comments)],
            ["Epoch.", "Earlier.", "ISO event.", "Latest."],
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.mod.main([target.url]), 0)
        discussion = output.getvalue().split("## Discussion\n", 1)[1].split("## Ending\n", 1)[0]
        self.assertEqual(
            discussion,
            "\n### Comment — ada\nEpoch.\n\n### Comment — ada\nEarlier.\n"
            "\n### Comment — ada\nLatest.\n\n",
        )
        self.assertIn("## Ending\nada: Latest.\n", output.getvalue())

    def test_bitbucket_server_malformed_epoch_dates_remain_undated(self):
        root = "https://git.example.com/rest/api/1.0/projects/KEY/repos/slug/pull-requests/4"
        self.forge.route(root, single({"id": 4, "title": "PR", "state": "OPEN"}))
        self.forge.route(f"{root}/changes", bitbucket_server_pager([], 2))
        invalid = [None, "", "not-a-date", {}, [], True, 1e100, "NaN", "Infinity"]
        activities = [
            {"comment": {"text": f"Undated {n}.", "createdDate": value}}
            for n, value in enumerate(invalid)
        ]
        activities.append({"comment": {"text": "Missing."}})
        activities.insert(0, {"comment": {
            "text": "Dated.", "author": {"name": "ada"}, "createdDate": -1000,
        }})
        self.forge.route(f"{root}/activities", bitbucket_server_pager(activities, 2))
        target = self.mod.parse_pr_url(
            "https://git.example.com/projects/KEY/repos/slug/pull-requests/4"
        )
        self.enterContext(patch.dict(self.mod.os.environ, {"BITBUCKET_TOKEN": "SYNTHETIC"}, clear=True))
        brief = self.mod.fetch_bitbucket_server_api(target)
        self.assertEqual(brief.comments[0].created, "1969-12-31T23:59:59+00:00")
        self.assertEqual([c.created for c in brief.comments[1:]], [None] * 10)
        self.assertEqual(
            [c.body for c in self.mod.chronological_events(brief.comments)],
            [f"Undated {n}." for n in range(9)] + ["Missing.", "Dated."],
        )
        self.assertIn("## Ending\nada: Dated.\n", self.mod.render(brief))

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


class GitFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def patch_run_cmd(self, fake):
        original = self.mod.run_cmd
        self.mod.run_cmd = fake
        self.addCleanup(setattr, self.mod, "run_cmd", original)

    def pick(self, listing: str, number: str = "7"):
        return self.mod.parse_pr_ref_listing(listing, number)

    def test_head_ref_beats_merge_ref_listed_first(self):
        listing = (
            "m111\trefs/pull/7/merge\n"
            "h222\trefs/pull/7/head\n"
        )
        self.assertEqual(self.pick(listing), ("h222", "refs/pull/7/head"))

    def test_head_ref_beats_merge_ref_listed_second(self):
        listing = (
            "h222\trefs/pull/7/head\n"
            "m111\trefs/pull/7/merge\n"
        )
        self.assertEqual(self.pick(listing), ("h222", "refs/pull/7/head"))

    def test_merge_only_listing_returns_merge_ref(self):
        listing = (
            "a000\trefs/heads/main\n"
            "m111\trefs/pull/7/merge\n"
        )
        self.assertEqual(self.pick(listing), ("m111", "refs/pull/7/merge"))

    def test_no_matching_ref_returns_none(self):
        listing = (
            "a000\tHEAD\n"
            "b111\trefs/pull/70/head\n"
            "c222\trefs/pull/17/head\n"
        )
        self.assertIsNone(self.pick(listing))

    def test_gitlab_merge_request_ref(self):
        listing = "g333\trefs/merge-requests/7/head\n"
        self.assertEqual(self.pick(listing), ("g333", "refs/merge-requests/7/head"))

    def test_bitbucket_pull_request_from_ref(self):
        listing = (
            "b444\trefs/pull-requests/7/merge\n"
            "b555\trefs/pull-requests/7/from\n"
        )
        self.assertEqual(self.pick(listing), ("b555", "refs/pull-requests/7/from"))

    def test_malformed_listing_lines_are_skipped(self):
        listing = "\njunk\nh222\trefs/pull/7/head\n"
        self.assertEqual(self.pick(listing), ("h222", "refs/pull/7/head"))

    def test_numstat_counts_and_binary_files(self):
        files = self.mod.parse_git_numstat(
            "10\t2\tsrc/auth.ts\n-\t-\tassets/logo.png\n"
        )
        self.assertEqual(
            [(f.path, f.additions, f.deletions) for f in files],
            [("src/auth.ts", 10, 2), ("assets/logo.png", None, None)],
        )

    def test_numstat_malformed_lines_are_skipped(self):
        files = self.mod.parse_git_numstat("\n3 1 spaces.txt\n4\tonly-two\n1\t0\tok.py\n")
        self.assertEqual([f.path for f in files], ["ok.py"])

    def test_brief_from_git_output(self):
        target = self.mod.Target(
            provider="github", host="github.com", number="7", owner="acme", repo="app"
        )
        brief = self.mod.brief_from_git(
            target,
            sha="h222",
            ref="refs/pull/7/head",
            remote_url="git@github.com:acme/app.git",
            log="abc1234 Fix auth middleware\ndef5678 wip\n",
            message="Fix auth middleware\n\nLonger body.\n",
            numstat="10\t2\tsrc/auth.ts\n",
        )
        self.assertEqual(brief.provider, "github")
        self.assertEqual(brief.url, "git@github.com:acme/app.git refs/pull/7/head")
        self.assertEqual(brief.title, "Fix auth middleware")
        self.assertEqual(brief.body, "Fix auth middleware\n\nLonger body.")
        self.assertEqual(brief.commits, ["abc1234 Fix auth middleware", "def5678 wip"])
        self.assertEqual(brief.head_sha, "h222")
        self.assertEqual(brief.repo, "acme/app")
        self.assertEqual(brief.source, "git")
        self.assertEqual([f.path for f in brief.files], ["src/auth.ts"])

    def test_brief_from_git_without_command_output(self):
        target = self.mod.Target(provider="unknown", host="example.com", number="7")
        brief = self.mod.brief_from_git(
            target, sha="h222", ref="refs/pull/7/head", remote_url="origin-url"
        )
        self.assertEqual(brief.provider, "git")
        self.assertEqual(brief.title, "PR/MR 7")
        self.assertEqual(brief.body, "")
        self.assertEqual(brief.commits, [])
        self.assertEqual(brief.files, [])

    def test_fetch_git_command_sequence(self):
        mod = self.mod
        calls = []
        outputs = {
            "remote": "origin\tgit@github.com:acme/app.git (fetch)\n",
            "ls-remote": "m111\trefs/pull/7/merge\nh222\trefs/pull/7/head\n",
            "fetch": "",
            "log": "abc1234 Fix auth\n",
            "diff": "1\t1\tREADME.md\n",
        }

        def fake(argv, cwd=None, timeout=45):
            calls.append(argv)
            if argv[1] == "log" and argv[2] == "-1":
                return "Fix auth\n"
            return outputs[argv[1]]

        self.patch_run_cmd(fake)
        target = mod.Target(provider="github", host="github.com", number="7")
        brief = mod.fetch_git(target, "/repo")
        local = "refs/resume-from-pr/7"
        self.assertEqual(
            calls,
            [
                ["git", "remote", "-v"],
                ["git", "ls-remote", "origin"],
                ["git", "fetch", "--quiet", "origin", f"refs/pull/7/head:{local}"],
                ["git", "log", "--format=%h %s", "-15", local],
                ["git", "log", "-1", "--format=%B", local],
                ["git", "diff", "--numstat", f"origin/HEAD...{local}"],
            ],
        )
        self.assertEqual(brief.title, "Fix auth")
        self.assertEqual(brief.head_sha, "h222")
        self.assertEqual([f.path for f in brief.files], ["README.md"])

    def test_fetch_git_reads_the_sha_when_the_ref_fetch_fails(self):
        mod = self.mod
        calls = []

        def fake(argv, cwd=None, timeout=45):
            calls.append(argv)
            if argv[1] == "remote":
                return "origin\tgit@github.com:acme/app.git (fetch)\n"
            if argv[1] == "ls-remote":
                return "h222\trefs/pull/7/head\n"
            raise mod.Skip("git failed")

        self.patch_run_cmd(fake)
        target = mod.Target(provider="github", host="github.com", number="7")
        brief = mod.fetch_git(target, "/repo")
        self.assertEqual(calls[3], ["git", "log", "--format=%h %s", "-15", "h222"])
        self.assertEqual(calls[5], ["git", "diff", "--numstat", "origin/HEAD...h222"])
        self.assertEqual(brief.title, "PR/MR 7")
        self.assertEqual(brief.files, [])


class CliFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_unparsed_argument_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.main(["not a pr"])
        self.assertIn("pull/merge request URL", str(ctx.exception))


# Issue #190: Bitbucket Cloud's pull-request payload abbreviates the head.
BITBUCKET_SHORT = "fe55684f21d5"
BITBUCKET_FULL = "fe55684f21d513aa09e86eaf639f3c6d3556d991"


class BitbucketHeadShaTests(unittest.TestCase):
    """head_sha must be a commit id git can fetch (issue #190)."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def setUp(self):
        self.forge = FakeForge(self, self.mod)

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

    def render_main(self, argv):
        return run_cli(self.mod.main, argv)

    def cloud_pr(self, digest, *, link=None):
        commit = {"hash": digest}
        if link is not None:
            commit["links"] = {"self": {"href": link}}
        return {
            "id": 11,
            "title": "Docs",
            "description": "Fix the README.",
            "state": "OPEN",
            "author": {"display_name": "Pat"},
            "source": {"branch": {"name": "docs"}, "commit": commit},
            "destination": {
                "branch": {"name": "master"},
                "repository": {"full_name": "ws/repo"},
            },
            "links": {"html": {"href": "https://bitbucket.org/ws/repo/pull-requests/11"}},
        }

    def route_cloud(self, payload, *, commit_body=None, commit_status=None):
        root = "https://api.bitbucket.org/2.0/repositories/ws/repo/pullrequests/11"
        self.forge.route(root, single(payload))
        for name in ("comments", "diffstat", "statuses"):
            self.forge.route(f"{root}/{name}", bitbucket_pager([], 2))
        link = (((payload.get("source") or {}).get("commit") or {}).get("links") or {}).get(
            "self", {}
        ).get("href")
        if link and commit_body is not None:
            self.forge.route(link, single(commit_body))
        elif link and commit_status is not None:
            self.forge.route(link, status(commit_status))
        self.forge.route(
            "https://api.bitbucket.org/2.0/repositories/ws/repo/pullrequests",
            single(
                {
                    "values": [
                        {
                            "id": 11,
                            "links": {
                                "html": {
                                    "href": "https://bitbucket.org/ws/repo/pull-requests/11"
                                }
                            },
                        }
                    ]
                }
            ),
        )
        return self.mod.parse_pr_url("https://bitbucket.org/ws/repo/pull-requests/11")

    def test_abbreviated_hash_renders_the_linked_commit_id(self):
        link = (
            "https://api.bitbucket.org/2.0/repositories/ws/repo/commit/" + BITBUCKET_SHORT
        )
        target = self.route_cloud(
            self.cloud_pr(BITBUCKET_SHORT, link=link),
            commit_body={"hash": BITBUCKET_FULL, "type": "commit"},
        )
        text = self.mod.render(self.mod.fetch_bitbucket_api(target))
        self.assertIn(f"head_sha: {BITBUCKET_FULL}\n", text)
        self.assertNotIn(f"head_sha: {BITBUCKET_SHORT}\n", text)
        self.assertIn("title: Docs\n", text)
        self.assertIn("head: docs\n", text)
        self.assertIn(link, self.forge.requests)

    def test_unsafe_commit_links_fail_without_publishing_an_abbreviation(self):
        self.enterContext(patch.dict(self.mod.os.environ, {"BITBUCKET_TOKEN": "SYNTHETIC"}, clear=True))
        for link in ("https://outside.invalid/commit", "https://api.bitbucket.org:444/commit",
                     "http://api.bitbucket.org/commit"):
            with self.subTest(link=link):
                self.forge.request_objects.clear()
                target = self.route_cloud(
                    self.cloud_pr(BITBUCKET_SHORT, link=link),
                    commit_body={"hash": BITBUCKET_FULL},
                )
                with self.assertRaisesRegex(self.mod.FetchError, "unsafe"):
                    self.mod.fetch_bitbucket_api(target)
                self.assertEqual(len(self.forge.request_objects), 1)
                self.assertEqual(self.forge.request_objects[0].get_header("Authorization"),
                                 "Bearer SYNTHETIC")

    def test_relative_commit_link_uses_the_pr_url_and_keeps_credentials(self):
        self.enterContext(patch.dict(self.mod.os.environ, {"BITBUCKET_TOKEN": "SYNTHETIC"}, clear=True))
        link = "../commit/" + BITBUCKET_SHORT
        target = self.route_cloud(self.cloud_pr(BITBUCKET_SHORT, link=link))
        absolute = "https://api.bitbucket.org/2.0/repositories/ws/repo/commit/" + BITBUCKET_SHORT
        self.forge.route(absolute, single({"hash": BITBUCKET_FULL}))
        brief = self.mod.fetch_bitbucket_api(target)
        self.assertEqual(brief.head_sha, BITBUCKET_FULL)
        request = next(r for r in self.forge.request_objects if r.full_url == absolute)
        self.assertEqual(request.get_header("Authorization"), "Bearer SYNTHETIC")

    def test_full_hash_is_unchanged_and_does_not_request_the_commit(self):
        link = "https://api.bitbucket.org/2.0/repositories/ws/repo/commit/" + BITBUCKET_FULL
        target = self.route_cloud(self.cloud_pr(BITBUCKET_FULL, link=link))
        brief = self.mod.fetch_bitbucket_api(target)
        self.assertEqual(brief.head_sha, BITBUCKET_FULL)
        self.assertNotIn(link, self.forge.requests)

    def test_unreadable_commit_link_raises_the_fetch_error(self):
        link = (
            "https://api.bitbucket.org/2.0/repositories/ws/repo/commit/" + BITBUCKET_SHORT
        )
        target = self.route_cloud(
            self.cloud_pr(BITBUCKET_SHORT, link=link), commit_status=404
        )
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.fetch_bitbucket_api(target)
        message = str(ctx.exception)
        self.assertIn(f"HTTP 404 for {link}", message)

    def test_missing_commit_link_does_not_publish_the_abbreviation(self):
        target = self.route_cloud(self.cloud_pr(BITBUCKET_SHORT))
        with self.assertRaises(self.mod.FetchError):
            self.mod.fetch_bitbucket_api(target)

    def test_url_number_and_current_branch_share_head_sha(self):
        link = (
            "https://api.bitbucket.org/2.0/repositories/ws/repo/commit/" + BITBUCKET_SHORT
        )
        self.route_cloud(
            self.cloud_pr(BITBUCKET_SHORT, link=link),
            commit_body={"hash": BITBUCKET_FULL, "type": "commit"},
        )
        url_text = self.render_main(["https://bitbucket.org/ws/repo/pull-requests/11"])
        self.patch_run_cmd(
            "origin\thttps://bitbucket.org/ws/repo.git (fetch)\n", branch="docs"
        )
        number_text = self.render_main(["--cwd", "workspace", "11"])
        branch_text = self.render_main(["--cwd", "workspace"])
        expected = f"head_sha: {BITBUCKET_FULL}\n"
        self.assertIn(expected, url_text)
        self.assertIn(expected, number_text)
        self.assertIn(expected, branch_text)
        self.assertNotIn(f"head_sha: {BITBUCKET_SHORT}\n", url_text)
        self.assertNotIn(f"head_sha: {BITBUCKET_SHORT}\n", number_text)
        self.assertNotIn(f"head_sha: {BITBUCKET_SHORT}\n", branch_text)

    def test_bitbucket_server_head_sha_is_latest_commit(self):
        root = (
            "https://git.example.com/rest/api/1.0/projects/KEY/repos/slug/pull-requests/4"
        )
        self.forge.route(
            root,
            single(
                {
                    "id": 4,
                    "title": "PR",
                    "state": "OPEN",
                    "fromRef": {"displayId": "feature", "latestCommit": "server-tip"},
                    "toRef": {"displayId": "master"},
                }
            ),
        )
        self.forge.route(f"{root}/changes", bitbucket_server_pager([], 2))
        self.forge.route(f"{root}/activities", bitbucket_server_pager([], 2))
        target = self.mod.parse_pr_url(
            "https://git.example.com/projects/KEY/repos/slug/pull-requests/4"
        )
        brief = self.mod.fetch_bitbucket_server_api(target)
        self.assertEqual(brief.head_sha, "server-tip")
        self.assertFalse(any("/commit/" in url for url in self.forge.requests))


def one_shot_server(testcase, reply):
    """Accept one request on localhost and answer it with reply(conn)."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    testcase.addCleanup(server.close)

    def run():
        conn, _ = server.accept()
        with conn:
            conn.recv(65536)
            reply(conn)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    testcase.addCleanup(thread.join, 5)
    return f"http://127.0.0.1:{server.getsockname()[1]}/api/v1/repos/o/r/pulls/1"


def reset_connection(conn):
    # A zero linger timeout makes close() send RST instead of FIN.
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))


def close_without_response(conn):
    pass


class DroppedConnectionTests(unittest.TestCase):
    """A host that drops the connection is a network error (issue #191)."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_connection_reset_is_a_network_error(self):
        url = one_shot_server(self, reset_connection)
        with self.assertRaises(self.mod.Skip) as ctx:
            self.mod.http_page(url)
        self.assertIn(f"network error for {url}", str(ctx.exception))

    def test_remote_close_before_response_is_a_network_error(self):
        url = one_shot_server(self, close_without_response)
        with self.assertRaises(self.mod.Skip) as ctx:
            self.mod.http_page(url)
        self.assertIn(f"network error for {url}", str(ctx.exception))

    def test_http_status_is_still_a_fetch_error(self):
        def not_found(conn):
            conn.sendall(
                b"HTTP/1.1 404 Not Found\r\nContent-Length: 2\r\n"
                b"Connection: close\r\n\r\n{}"
            )

        url = one_shot_server(self, not_found)
        with self.assertRaises(self.mod.FetchError) as ctx:
            self.mod.http_page(url)
        self.assertIn(f"HTTP 404 for {url}", str(ctx.exception))

    def test_success_still_returns_the_body(self):
        def ok(conn):
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\nX-Total: 3\r\n"
                b"Connection: close\r\n\r\n{\"id\": 42}\n"
            )

        url = one_shot_server(self, ok)
        body, headers = self.mod.http_page(url)
        self.assertEqual(body, {"id": 42})
        self.assertEqual(headers["x-total"], "3")

    def test_cli_reports_a_dropped_connection_in_one_line(self):
        mod = self.mod

        def dropped(request, timeout=30):
            raise http.client.RemoteDisconnected(
                "Remote end closed connection without response"
            )

        def no_git(argv, cwd=None, timeout=45):
            raise mod.Skip("git unavailable")

        original_opener = mod.urllib.request.build_opener
        mod.urllib.request.build_opener = lambda *handlers: SimpleNamespace(open=dropped)
        self.addCleanup(setattr, mod.urllib.request, "build_opener", original_opener)
        original_run_cmd = mod.run_cmd
        mod.run_cmd = no_git
        self.addCleanup(setattr, mod, "run_cmd", original_run_cmd)

        pr = "https://codeberg.org/forgejo/forgejo/pulls/14781"
        with self.assertRaises(SystemExit) as ctx:
            mod.main([pr])
        message = str(ctx.exception)
        self.assertTrue(
            message.startswith(f"Gitea/Forgejo: failed to fetch pull/merge request {pr}: "),
            message,
        )
        self.assertIn(
            "network error for https://codeberg.org/api/v1/repos/forgejo/forgejo/pulls/14781",
            message,
        )


class NormalizeCheckStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_success_mappings(self):
        cases = ["SUCCESS", "success", "successful", "SUCCESSFUL", "succeeded", "SUCCEEDED", "passed", "PASSED"]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.mod.normalize_check_status(case), "success")

    def test_failure_mappings(self):
        cases = [
            "FAILURE", "failure", "failed", "FAILED",
            "timed_out", "TIMED_OUT", "timedout", "TIMEDOUT",
            "partiallySucceeded", "partially_succeeded", "PARTIALLY_SUCCEEDED",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.mod.normalize_check_status(case), "failure")

    def test_pending_mappings(self):
        cases = [
            "PENDING", "pending", "in_progress", "IN_PROGRESS", "inprogress", "INPROGRESS",
            "running", "RUNNING", "queued", "QUEUED", "created", "waiting_for_resource",
            "preparing", "scheduled", "manual", "expected", "notStarted", "not_started",
            "requested", "waiting", "notSet", "not_set",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.mod.normalize_check_status(case), "pending")

    def test_canceled_mappings(self):
        cases = [
            "CANCELLED", "cancelled", "canceled", "CANCELED",
            "STOPPED", "stopped", "cancelling", "aborted",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.mod.normalize_check_status(case), "canceled")

    def test_skipped_mappings(self):
        cases = [
            "SKIPPED", "skipped", "neutral", "NEUTRAL",
            "notApplicable", "NOTAPPLICABLE", "not_applicable", "ignored",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.mod.normalize_check_status(case), "skipped")

    def test_error_mappings(self):
        cases = ["ERROR", "error"]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.mod.normalize_check_status(case), "error")

    def test_action_required_mappings(self):
        cases = ["ACTION_REQUIRED", "action_required", "actionrequired"]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.mod.normalize_check_status(case), "action_required")

    def test_unknown_mappings(self):
        cases = ["", "   ", None, "unknown", "UNKNOWN", "unexpected_provider_state"]
        for case in cases:
            with self.subTest(case=case):
                result = self.mod.normalize_check_status(case)
                self.assertEqual(result, "unknown")
                self.assertNotEqual(result, "success")

    def test_idempotent_canonical_statuses(self):
        canonical = [
            "success", "failure", "pending", "canceled",
            "skipped", "error", "action_required", "unknown",
        ]
        for s in canonical:
            with self.subTest(status=s):
                self.assertEqual(self.mod.normalize_check_status(s), s)


class ForgeCheckConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()
        cls.target = cls.mod.Target("github", "github.com", "9")

    def test_github_view_check_construction_and_details(self):
        data = {
            "title": "T",
            "number": 1,
            "statusCheckRollup": [
                {"name": "run-ci", "conclusion": "SUCCESS", "detailsUrl": "https://ci.example.com/run"},
                {"context": "status-ci", "state": "FAILURE", "targetUrl": "https://ci.example.com/status"},
                {"name": "no-url", "conclusion": "NEUTRAL"},
            ],
        }
        brief = self.mod.brief_from_github_view(data, target=self.target)
        self.assertEqual(len(brief.checks), 3)
        self.assertEqual(brief.checks[0].name, "run-ci")
        self.assertEqual(brief.checks[0].status, "success")
        self.assertEqual(brief.checks[0].details, "https://ci.example.com/run")
        self.assertEqual(brief.checks[1].name, "status-ci")
        self.assertEqual(brief.checks[1].status, "failure")
        self.assertEqual(brief.checks[1].details, "https://ci.example.com/status")
        self.assertEqual(brief.checks[2].name, "no-url")
        self.assertEqual(brief.checks[2].status, "skipped")
        self.assertIsNone(brief.checks[2].details)

    def test_github_rest_check_construction_and_details(self):
        pr = {"number": 1, "title": "T", "state": "open"}
        statuses = [
            {"context": "status-ci", "state": "success", "target_url": "https://ci.example.com/s"},
            {"context": "status-no-url", "state": "error"},
        ]
        check_runs = [
            {"name": "run-ci", "status": "completed", "conclusion": "action_required", "details_url": "https://ci.example.com/r"},
            {"name": "run-no-url", "status": "in_progress", "conclusion": None},
        ]
        brief = self.mod.brief_from_github_rest(
            pr, target=self.target, statuses=statuses, check_runs=check_runs
        )
        self.assertEqual(len(brief.checks), 4)
        self.assertEqual(brief.checks[0].status, "success")
        self.assertEqual(brief.checks[0].details, "https://ci.example.com/s")
        self.assertEqual(brief.checks[1].status, "error")
        self.assertIsNone(brief.checks[1].details)
        self.assertEqual(brief.checks[2].status, "action_required")
        self.assertEqual(brief.checks[2].details, "https://ci.example.com/r")
        self.assertEqual(brief.checks[3].status, "pending")
        self.assertIsNone(brief.checks[3].details)

    def test_gitlab_check_construction_and_details(self):
        mr_with_url = {
            "iid": 1,
            "title": "T",
            "state": "opened",
            "head_pipeline": {"status": "canceled", "web_url": "https://gitlab.com/ci/1"},
        }
        brief = self.mod.brief_from_gitlab(mr_with_url)
        self.assertEqual(len(brief.checks), 1)
        self.assertEqual(brief.checks[0].name, "pipeline")
        self.assertEqual(brief.checks[0].status, "canceled")
        self.assertEqual(brief.checks[0].details, "https://gitlab.com/ci/1")

        mr_no_url = {
            "iid": 2,
            "title": "T",
            "state": "opened",
            "head_pipeline": {"status": "running"},
        }
        brief_no_url = self.mod.brief_from_gitlab(mr_no_url)
        self.assertEqual(brief_no_url.checks[0].status, "pending")
        self.assertIsNone(brief_no_url.checks[0].details)

    def test_bitbucket_check_construction_and_details(self):
        pr = {
            "id": 1,
            "title": "T",
            "state": "OPEN",
            "links": {"html": {"href": "https://bitbucket.org/w/r/pull-requests/1"}},
        }
        statuses = [
            {"name": "build", "state": "STOPPED", "url": "https://ci.example.com/build/1"},
            {"key": "lint", "state": "SUCCESSFUL", "links": {"html": {"href": "https://ci.example.com/lint/1"}}},
            {"name": "test", "state": "INPROGRESS"},
        ]
        brief = self.mod.brief_from_bitbucket(pr, statuses=statuses)
        self.assertEqual(len(brief.checks), 3)
        self.assertEqual(brief.checks[0].name, "build")
        self.assertEqual(brief.checks[0].status, "canceled")
        self.assertEqual(brief.checks[0].details, "https://ci.example.com/build/1")
        self.assertEqual(brief.checks[1].name, "lint")
        self.assertEqual(brief.checks[1].status, "success")
        self.assertEqual(brief.checks[1].details, "https://ci.example.com/lint/1")
        self.assertEqual(brief.checks[2].name, "test")
        self.assertEqual(brief.checks[2].status, "pending")
        self.assertIsNone(brief.checks[2].details)

    def test_azure_check_construction_and_details(self):
        pr = {
            "pullRequestId": 1,
            "title": "T",
            "status": "active",
        }
        statuses = [
            {"context": {"name": "ci"}, "state": "succeeded", "targetUrl": "https://dev.azure.com/b/1"},
            {"description": "audit", "state": "notApplicable"},
            {"context": {"name": "gates"}, "state": "error", "targetUrl": "https://dev.azure.com/g/1"},
        ]
        brief = self.mod.brief_from_azure(pr, statuses=statuses)
        self.assertEqual(len(brief.checks), 3)
        self.assertEqual(brief.checks[0].name, "ci")
        self.assertEqual(brief.checks[0].status, "success")
        self.assertEqual(brief.checks[0].details, "https://dev.azure.com/b/1")
        self.assertEqual(brief.checks[1].name, "audit")
        self.assertEqual(brief.checks[1].status, "skipped")
        self.assertIsNone(brief.checks[1].details)
        self.assertEqual(brief.checks[2].name, "gates")
        self.assertEqual(brief.checks[2].status, "error")
        self.assertEqual(brief.checks[2].details, "https://dev.azure.com/g/1")


class ForgeEndingSummariesAndRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()
        cls.target = cls.mod.Target("github", "github.com", "9")

    def test_gitlab_cancellation_ending_and_render(self):
        for status_spelling in ("canceled", "cancelled"):
            with self.subTest(spelling=status_spelling):
                mr = {
                    "iid": 1,
                    "title": "Fix something",
                    "state": "opened",
                    "head_pipeline": {"status": status_spelling, "web_url": "https://gitlab.com/ci/1"},
                }
                brief = self.mod.brief_from_gitlab(mr)
                self.assertEqual(self.mod.ending_text(brief), "Failing checks: pipeline")
                text = self.mod.render(brief)
                self.assertIn("- pipeline: canceled — https://gitlab.com/ci/1", text)
                self.assertIn("## Ending\nFailing checks: pipeline", text)

    def test_bitbucket_stopped_ending_and_render(self):
        pr = {
            "id": 1,
            "title": "Fix something",
            "state": "OPEN",
            "links": {"html": {"href": "https://bitbucket.org/w/r/pull-requests/1"}},
        }
        statuses = [
            {"name": "build", "state": "STOPPED", "url": "https://ci.example.com/build/1"}
        ]
        brief = self.mod.brief_from_bitbucket(pr, statuses=statuses)
        self.assertEqual(self.mod.ending_text(brief), "Failing checks: build")
        text = self.mod.render(brief)
        self.assertIn("- build: canceled — https://ci.example.com/build/1", text)
        self.assertIn("## Ending\nFailing checks: build", text)

    def test_azure_cancellation_ending_and_render(self):
        for status_spelling in ("canceled", "cancelled"):
            with self.subTest(spelling=status_spelling):
                pr = {
                    "pullRequestId": 1,
                    "title": "Fix something",
                    "status": "active",
                }
                statuses = [
                    {"context": {"name": "ci"}, "state": status_spelling, "targetUrl": "https://dev.azure.com/b/1"}
                ]
                brief = self.mod.brief_from_azure(pr, statuses=statuses)
                self.assertEqual(self.mod.ending_text(brief), "Failing checks: ci")
                text = self.mod.render(brief)
                self.assertIn("- ci: canceled — https://dev.azure.com/b/1", text)
                self.assertIn("## Ending\nFailing checks: ci", text)

    def test_review_precedence_preserved_over_failing_checks(self):
        # When reviewDecision is CHANGES_REQUESTED, review decision wins over failing check.
        data = {
            "title": "T",
            "number": 1,
            "reviewDecision": "CHANGES_REQUESTED",
            "reviews": [
                {
                    "body": "Need changes",
                    "state": "CHANGES_REQUESTED",
                    "author": {"login": "reviewer"},
                }
            ],
            "statusCheckRollup": [
                {"name": "ci", "conclusion": "FAILURE"}
            ],
        }
        brief = self.mod.brief_from_github_view(data, target=self.target)
        ending = self.mod.ending_text(brief)
        self.assertTrue(ending.startswith("Changes Requested"))
        self.assertNotIn("Failing checks", ending)

        # When reviewDecision is APPROVED, review decision wins over failing/stopped check.
        data_approved = {
            "title": "T",
            "number": 2,
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [
                {"name": "ci", "conclusion": "CANCELLED"}
            ],
        }
        brief_approved = self.mod.brief_from_github_view(data_approved, target=self.target)
        self.assertEqual(self.mod.ending_text(brief_approved), "Approved")

    def test_action_required_included_in_failing_checks(self):
        data = {
            "title": "T",
            "number": 1,
            "statusCheckRollup": [
                {"name": "cla-check", "conclusion": "ACTION_REQUIRED"}
            ],
        }
        brief = self.mod.brief_from_github_view(data, target=self.target)
        self.assertEqual(self.mod.ending_text(brief), "Failing checks: cla-check")


class CredentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def setUp(self):
        self.enterContext(patch.dict(self.mod.os.environ, {}, clear=True))

    def test_authentication_schemes_and_variable_precedence(self):
        cases = (
            ("github", ("GH_TOKEN", "GITHUB_TOKEN"),
             {"Authorization": "Bearer secret"}),
            ("gitlab", ("GITLAB_TOKEN", "GL_TOKEN", "PRIVATE_TOKEN"),
             {"PRIVATE-TOKEN": "secret"}),
            ("bitbucket", ("BITBUCKET_TOKEN", "BITBUCKET_ACCESS_TOKEN"),
             {"Authorization": "Bearer secret"}),
            ("bitbucket-server", ("BITBUCKET_TOKEN", "BITBUCKET_ACCESS_TOKEN"),
             {"Authorization": "Bearer secret"}),
            ("gitea", ("GITEA_TOKEN", "FORGEJO_TOKEN", "CODEBERG_TOKEN"),
             {"Authorization": "token secret"}),
            ("azure", ("AZURE_DEVOPS_TOKEN", "SYSTEM_ACCESSTOKEN", "AZURE_TOKEN"),
             {"Authorization": "Basic OnNlY3JldA=="}),
        )
        for provider, names, expected in cases:
            with self.subTest(provider=provider, credentials="absent"):
                self.assertEqual(self.mod.auth_headers(provider), {})
            for index, name in enumerate(names):
                env = {key: "later" for key in names[index + 1:]}
                env.update({key: "" for key in names[:index]})
                env[name] = "secret"
                with self.subTest(provider=provider, variable=name), patch.dict(
                    self.mod.os.environ, env, clear=True
                ):
                    self.assertEqual(self.mod.auth_headers(provider), expected)
                    self.assertIsNone(self.mod.credential_hint(provider))

    def test_bitbucket_basic_requires_both_fields_and_prefers_tokens(self):
        for name in ("BITBUCKET_APP_PASSWORD", "BITBUCKET_PASSWORD"):
            with self.subTest(password=name):
                for env, expected in (
                    ({"BITBUCKET_USERNAME": "user"}, {}),
                    ({name: "secret"}, {}),
                    ({"BITBUCKET_USERNAME": "user", name: "secret"},
                     {"Authorization": "Basic dXNlcjpzZWNyZXQ="}),
                    ({"BITBUCKET_USERNAME": "user", name: "secret",
                      "BITBUCKET_TOKEN": "token"},
                     {"Authorization": "Bearer token"}),
                ):
                    with patch.dict(self.mod.os.environ, env, clear=True):
                        for provider in ("bitbucket", "bitbucket-server"):
                            self.assertEqual(self.mod.auth_headers(provider), expected)
                            if expected:
                                self.assertIsNone(self.mod.credential_hint(provider))
                            else:
                                self.assertIn("BITBUCKET_USERNAME with either BITBUCKET_APP_PASSWORD or BITBUCKET_PASSWORD",
                                              self.mod.credential_hint(provider))
        with patch.dict(self.mod.os.environ, {
            "BITBUCKET_USERNAME": "user",
            "BITBUCKET_APP_PASSWORD": "secret",
            "BITBUCKET_PASSWORD": "later",
        }):
            for provider in ("bitbucket", "bitbucket-server"):
                self.assertEqual(self.mod.auth_headers(provider),
                                 {"Authorization": "Basic dXNlcjpzZWNyZXQ="})

    def test_hints_name_every_variable_read_for_each_provider(self):
        for provider in self.mod.PROVIDERS:
            with self.subTest(provider=provider.name):
                hint = self.mod.credential_hint(provider.name)
                self.assertIn(provider.label, hint)
                for credential in provider.credentials:
                    for name in credential.variables:
                        self.assertIn(name, hint)
                    if credential.username_variable:
                        self.assertIn(credential.username_variable, hint)
        self.assertEqual(self.mod.auth_headers("unknown"), {})
        self.assertIsNone(self.mod.credential_hint("unknown"))

    def test_cli_url_and_branch_failures_for_every_provider(self):
        cases = (
            ("https://github.com/g/p/pull/3", "git@github.com:g/p.git", {"GH_TOKEN": "SYNTHETIC"}),
            ("https://gitlab.com/g/p/-/merge_requests/3", "git@gitlab.com:g/p.git", {"GITLAB_TOKEN": "SYNTHETIC"}),
            ("https://bitbucket.org/g/p/pull-requests/3", "git@bitbucket.org:g/p.git", {"BITBUCKET_TOKEN": "SYNTHETIC"}),
            ("https://git.example.com/projects/KEY/repos/p/pull-requests/3", "https://git.example.com/scm/KEY/p.git",
             {"BITBUCKET_USERNAME": "user", "BITBUCKET_PASSWORD": "SYNTHETIC"}),
            ("https://codeberg.org/g/p/pulls/3", "git@codeberg.org:g/p.git", {"GITEA_TOKEN": "SYNTHETIC"}),
            ("https://dev.azure.com/org/project/_git/p/pullrequest/3", "git@ssh.dev.azure.com:v3/org/project/p",
             {"AZURE_DEVOPS_TOKEN": "SYNTHETIC"}),
        )
        FakeForge(self, self.mod)
        for url, remote, credentials in cases:
            provider = self.mod.parse_pr_url(url).provider
            for env in ({}, credentials):
                for args in ([url], []):
                    with self.subTest(provider=provider, credentials=bool(env), url=bool(args)), patch.dict(
                        self.mod.os.environ, env, clear=True
                    ), patch.object(self.mod, "git_current_branch", return_value="feature/x"), patch.object(
                        self.mod, "git_remotes", return_value=[("origin", remote)]
                    ), patch.object(self.mod, "run_cmd", side_effect=self.mod.Skip("no CLI")):
                        with self.assertRaises(SystemExit) as caught:
                            self.mod.main(args)
                        message = str(caught.exception)
                        self.assertIn(self.mod.PROVIDER_LABELS[provider], message)
                        self.assertIn("HTTP 404", message)
                        self.assertNotIn("SYNTHETIC", message)
                        if env:
                            self.assertNotIn("for private", message)
                        else:
                            self.assertIn("for private", message)
                            for name in credentials:
                                self.assertIn(name, message)

    def test_gitlab_url_failure_names_credentials_only_when_missing(self):
        target = self.mod.parse_pr_url("https://gitlab.com/g/p/-/merge_requests/3")
        FakeForge(self, self.mod).route(
            "https://gitlab.com/api/v4/projects/g%2Fp/merge_requests/3", status(404)
        )
        for env in ({}, {"GITLAB_TOKEN": "SYNTHETIC"}):
            with self.subTest(credentials=bool(env)), patch.dict(
                self.mod.os.environ, env, clear=True
            ), patch.object(self.mod, "run_cmd", side_effect=self.mod.Skip("no CLI")):
                with self.assertRaises(self.mod.FetchError) as caught:
                    self.mod.fetch_brief(target, None)
                message = str(caught.exception)
                self.assertIn("GitLab: failed to fetch", message)
                self.assertIn("HTTP 404", message)
                self.assertNotIn("SYNTHETIC", message)
                if env:
                    self.assertNotIn("GITLAB_TOKEN", message)
                else:
                    self.assertIn("GITLAB_TOKEN", message)

    def test_branch_failure_names_credentials_only_when_missing(self):
        remote = self.mod.Repo("gitlab", "gitlab.com", "g", "p", "g/p")
        for env in ({}, {"GITLAB_TOKEN": "SYNTHETIC"}):
            with self.subTest(credentials=bool(env)), patch.dict(
                self.mod.os.environ, env, clear=True
            ):
                message = str(self.mod._branch_lookup_failure(
                    "gitlab", remote, "feature/x", "HTTP 404: Not Found"
                ))
                self.assertIn("branch 'feature/x'", message)
                self.assertIn("HTTP 404: Not Found", message)
                self.assertNotIn("SYNTHETIC", message)
                if env:
                    self.assertNotIn("GITLAB_TOKEN", message)
                else:
                    self.assertIn("GITLAB_TOKEN", message)


if __name__ == "__main__":
    unittest.main()
