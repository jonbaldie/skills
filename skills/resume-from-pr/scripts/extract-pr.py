#!/usr/bin/env python3
"""Extract a resume brief from a pull request or merge request.

Accepts a host URL, a number in the current repo, or (with no argument) the
open PR/MR for the current branch. GitHub, GitLab, Bitbucket, Gitea/Forgejo,
and Azure DevOps have first-class fetchers; other hosts fall through to git
PR refs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


class Skip(Exception):
    """Try the next fetcher."""


class FetchError(Exception):
    """Stop this provider path."""


def truncate(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s)>\]]+", text, flags=re.I)
    if not match:
        return None
    # Trim trailing sentence punctuation, quotes, and backticks from prose-embedded URLs.
    return match.group(0).rstrip(".,;:!?\"'`")


def strip_wrap(text: str) -> str:
    text = text.strip()
    if (
        (text.startswith("<") and text.endswith(">"))
        or (text.startswith('"') and text.endswith('"'))
        or (text.startswith("'") and text.endswith("'"))
        or (text.startswith("`") and text.endswith("`"))
    ):
        return text[1:-1].strip()
    md = re.fullmatch(r"\[([^\]]*)\]\((https?://[^)]+)\)", text)
    if md:
        return md.group(2)
    return text


def normalize_web_url(url: str) -> str:
    url = url.strip()
    url = url.split("#", 1)[0].split("?", 1)[0]
    url = re.sub(r"\.(diff|patch)$", "", url, flags=re.I)
    url = url.rstrip("/")
    url = re.sub(
        r"/(?:files|commits|checks|diffs?|changes|conversations|activity|"
        r"pipelines|commits/.+|overview|v4/diff)$",
        "",
        url,
        flags=re.I,
    )
    return url


def ensure_scheme(text: str) -> str:
    if re.match(r"^https?://", text, flags=re.I):
        return text
    if re.match(r"^[\w.-]+\.[A-Za-z]{2,}/", text):
        return "https://" + text
    return text


# ---------------------------------------------------------------------------
# Target
# ---------------------------------------------------------------------------


@dataclass
class Target:
    provider: str
    host: str
    number: str
    url: str | None = None
    owner: str | None = None
    repo: str | None = None
    project: str | None = None  # Azure DevOps project, GitLab full path
    org: str | None = None
    original: str | None = None

    @property
    def slug(self) -> str | None:
        if self.project:
            return self.project
        if self.owner and self.repo:
            return f"{self.owner}/{self.repo}"
        return self.owner


# Path-shape classifiers — host-agnostic so self-hosted forges work.
_AZURE = re.compile(
    r"^https?://(?:dev\.azure\.com/(?P<org>[^/]+)/(?:(?P<project>[^/]+)/)?"
    r"_git/(?P<repo>[^/]+)|(?P<org2>[^./]+)\.visualstudio\.com/"
    r"(?:(?P<project2>[^/]+)/)?_git/(?P<repo2>[^/]+))/pullrequest/(?P<num>\d+)",
    re.I,
)
_BB_SERVER = re.compile(
    r"^https?://(?P<host>[^/]+)/projects/(?P<key>[^/]+)/repos/(?P<slug>[^/]+)"
    r"/pull-requests/(?P<num>\d+)",
    re.I,
)
_GITLAB = re.compile(
    r"^https?://(?P<host>[^/]+)/(?P<path>.+?)/-/merge_requests/(?P<num>\d+)",
    re.I,
)
_GITLAB_LEGACY = re.compile(
    r"^https?://(?P<host>[^/]+)/(?P<path>.+)/merge_requests/(?P<num>\d+)",
    re.I,
)
_BITBUCKET = re.compile(
    r"^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"/pull-requests/(?P<num>\d+)",
    re.I,
)
_GITEA = re.compile(
    r"^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pulls/(?P<num>\d+)",
    re.I,
)
_GITHUB = re.compile(
    r"^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<num>\d+)",
    re.I,
)
_SHORTHAND_GH = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)[#/](?P<num>\d+)$"
)
_SHORTHAND_GL = re.compile(
    r"^(?P<path>[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)!(?P<num>\d+)$"
)
_NUMBER = re.compile(r"^#?(?P<num>\d+)$")
_GITLAB_BANG = re.compile(r"^!(?P<num>\d+)$")
# Remote path shapes for providers without a hostname giveaway.
_AZURE_REMOTE_HTTPS = re.compile(
    r"^(?P<org>[^/]+)/(?P<project>[^/]+)/_git/(?P<repo>.+)$"
)
_AZURE_REMOTE_SHORT = re.compile(r"^(?P<org>[^/]+)/_git/(?P<repo>.+)$")
_AZURE_REMOTE_VS = re.compile(r"^(?:(?P<project>[^/]+)/)?_git/(?P<repo>.+)$")
_AZURE_REMOTE_SSH = re.compile(r"^v3/(?P<org>[^/]+)/(?P<project>[^/]+)/(?P<repo>.+)$")
_BITBUCKET_SERVER_REMOTE = re.compile(
    r"^(?:projects/(?P<key>[^/]+)/repos/(?P<slug>[^/]+)"
    r"|scm/(?P<key2>[^/]+)/(?P<slug2>[^/]+))$"
)


def parse_pr_url(url: str) -> Target:
    raw = normalize_web_url(ensure_scheme(strip_wrap(url)))
    m = _AZURE.match(raw)
    if m:
        org = m.group("org") or m.group("org2")
        project = m.group("project") or m.group("project2") or org
        repo = m.group("repo") or m.group("repo2")
        host = "dev.azure.com" if m.group("org") else f"{m.group('org2')}.visualstudio.com"
        return Target(
            provider="azure",
            host=host,
            number=m.group("num"),
            url=raw,
            owner=org,
            repo=repo,
            project=urllib.parse.unquote(project),
            org=urllib.parse.unquote(org),
            original=url,
        )
    m = _BB_SERVER.match(raw)
    if m:
        return Target(
            provider="bitbucket-server",
            host=m.group("host"),
            number=m.group("num"),
            url=raw,
            owner=m.group("key"),
            repo=m.group("slug"),
            original=url,
        )
    m = _GITLAB.match(raw)
    if m:
        path = urllib.parse.unquote(m.group("path"))
        owner, repo = split_path(path)
        return Target(
            provider="gitlab",
            host=m.group("host"),
            number=m.group("num"),
            url=raw,
            owner=owner,
            repo=repo,
            project=path,
            original=url,
        )
    m = _GITLAB_LEGACY.match(raw)
    if m and "/-/" not in raw:
        path = urllib.parse.unquote(m.group("path"))
        owner, repo = split_path(path)
        return Target(
            provider="gitlab",
            host=m.group("host"),
            number=m.group("num"),
            url=raw,
            owner=owner,
            repo=repo,
            project=path,
            original=url,
        )
    m = _BITBUCKET.match(raw)
    if m:
        return Target(
            provider="bitbucket",
            host=m.group("host"),
            number=m.group("num"),
            url=raw,
            owner=m.group("owner"),
            repo=m.group("repo"),
            original=url,
        )
    m = _GITEA.match(raw)
    if m:
        return Target(
            provider="gitea",
            host=m.group("host"),
            number=m.group("num"),
            url=raw,
            owner=m.group("owner"),
            repo=m.group("repo"),
            original=url,
        )
    m = _GITHUB.match(raw)
    if m:
        host = m.group("host")
        provider = "github" if host.lower() in {"github.com", "www.github.com"} else "github"
        return Target(
            provider=provider,
            host=host,
            number=m.group("num"),
            url=raw,
            owner=m.group("owner"),
            repo=m.group("repo"),
            original=url,
        )
    raise FetchError(f"Could not parse as a pull/merge request URL: {url}")


def split_path(path: str) -> tuple[str, str]:
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return path, path
    return "/".join(parts[:-1]), parts[-1]


def parse_git_remote(url: str) -> tuple[str, str]:
    """Return (host, owner/repo path) from a git remote URL."""
    text = url.strip()
    text = re.sub(r"\.git$", "", text)
    if text.startswith("git@"):
        # git@host:path
        rest = text[4:]
        host, _, path = rest.partition(":")
        return host, path.lstrip("/")
    parsed = urllib.parse.urlparse(ensure_scheme(text) if "://" in text else text)
    if parsed.scheme in {"http", "https", "ssh", "git"}:
        host = parsed.hostname or ""
        path = parsed.path.lstrip("/")
        return host, path
    scp = re.match(r"^[^@]+@([^:]+):(.+)$", text)
    if scp:
        return scp.group(1), scp.group(2).lstrip("/")
    raise FetchError(f"Could not parse git remote: {url}")


def parse_argument(arg: str) -> Target | str:
    """Return a Target, or 'number:N' / 'current' sentinel strings for cwd resolve."""
    text = strip_wrap(arg)
    embedded = first_url(text)
    if embedded:
        return parse_pr_url(embedded)
    m = _SHORTHAND_GL.match(text)
    if m:
        path = m.group("path")
        owner, repo = split_path(path)
        return Target(
            provider="gitlab",
            host="gitlab.com",
            number=m.group("num"),
            owner=owner,
            repo=repo,
            project=path,
            original=arg,
        )
    m = _SHORTHAND_GH.match(text)
    if m:
        return Target(
            provider="github",
            host="github.com",
            number=m.group("num"),
            owner=m.group("owner"),
            repo=m.group("repo"),
            url=f"https://github.com/{m.group('owner')}/{m.group('repo')}/pull/{m.group('num')}",
            original=arg,
        )
    m = _GITLAB_BANG.match(text)
    if m:
        return Target(provider="unknown", host="", number=m.group("num"), original=arg)
    m = _NUMBER.match(text)
    if m:
        return Target(provider="unknown", host="", number=m.group("num"), original=arg)
    if re.match(r"^https?://", ensure_scheme(text), flags=re.I) or re.match(
        r"^[\w.-]+\.[A-Za-z]{2,}/", text
    ):
        return parse_pr_url(text)
    raise FetchError(
        "Pass a pull/merge request URL (GitHub, GitLab, Bitbucket, "
        "Gitea/Forgejo, Azure DevOps, or any host with a PR/MR link)."
    )


# ---------------------------------------------------------------------------
# Brief
# ---------------------------------------------------------------------------


@dataclass
class Comment:
    author: str
    body: str
    created: str | None = None
    path: str | None = None
    line: int | None = None
    kind: str = "discussion"  # discussion | review | inline


@dataclass
class FileChange:
    path: str
    additions: int | None = None
    deletions: int | None = None
    change_type: str | None = None


@dataclass
class Check:
    name: str
    status: str
    details: str | None = None


@dataclass
class Brief:
    provider: str
    url: str
    number: str
    title: str
    state: str
    author: str
    body: str = ""
    draft: bool = False
    base: str | None = None
    head: str | None = None
    head_sha: str | None = None
    repo: str | None = None
    host: str | None = None
    review_decision: str | None = None
    source: str = ""
    files: list[FileChange] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    linked_issues: list[str] = field(default_factory=list)
    fork: bool = False


def login_of(obj: Any, *keys: str) -> str:
    if isinstance(obj, str):
        return obj
    if not isinstance(obj, dict):
        return ""
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested = login_of(value, "login", "username", "display_name", "name")
            if nested:
                return nested
    return ""


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a provider ISO timestamp into an aware datetime, else None."""
    if not value:
        return None
    text = value.strip()
    if text.upper().endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def chronological_events(comments: list[Comment]) -> list[Comment]:
    """Merge review and discussion events, ordered by provider timestamp.

    Events without a parseable timestamp sort first, keeping their insertion
    order, without disturbing the relative order of timestamped events.
    """
    events = [c for c in comments if c.kind in ("review", "discussion")]
    floor = datetime(1, 1, 1, tzinfo=timezone.utc)
    return sorted(events, key=lambda c: parse_timestamp(c.created) or floor)


def render(brief: Brief) -> str:
    lines: list[str] = []
    lines.append("# Pull request brief")
    lines.append(f"provider: {brief.provider}")
    if brief.source:
        lines.append(f"source: {brief.source}")
    lines.append(f"url: {brief.url}")
    lines.append(f"number: {brief.number}")
    if brief.repo:
        lines.append(f"repo: {brief.repo}")
    if brief.host:
        lines.append(f"host: {brief.host}")
    lines.append(f"title: {brief.title}")
    lines.append(f"state: {brief.state}")
    lines.append(f"draft: {str(brief.draft).lower()}")
    if brief.author:
        lines.append(f"author: {brief.author}")
    if brief.base:
        lines.append(f"base: {brief.base}")
    if brief.head:
        lines.append(f"head: {brief.head}")
    if brief.head_sha:
        lines.append(f"head_sha: {brief.head_sha}")
    if brief.fork:
        lines.append("fork: true")
    if brief.review_decision:
        lines.append(f"review_decision: {brief.review_decision}")
    if brief.labels:
        lines.append("labels: " + ", ".join(brief.labels))

    if brief.body.strip():
        lines.append("")
        lines.append("## Goal")
        lines.append("")
        lines.append(truncate(brief.body, 3000))

    if brief.linked_issues:
        lines.append("")
        lines.append("## Linked issues")
        for issue in brief.linked_issues:
            lines.append(f"- {issue}")

    if brief.commits:
        lines.append("")
        lines.append("## Commits")
        for commit in brief.commits[:15]:
            lines.append(f"- {commit}")

    if brief.files:
        lines.append("")
        lines.append("## Files in play")
        for item in brief.files[:40]:
            extra = ""
            if item.additions is not None or item.deletions is not None:
                extra = f" (+{item.additions or 0}/-{item.deletions or 0})"
            kind = f" {item.change_type}" if item.change_type else ""
            lines.append(f"- {item.path}{extra}{kind}")

    inline = [c for c in brief.comments if c.kind == "inline"]
    reviews = [c for c in brief.comments if c.kind == "review"]
    discussion = [c for c in brief.comments if c.kind == "discussion"]
    events = chronological_events(brief.comments)

    if inline:
        lines.append("")
        lines.append("## Review threads")
        for comment in inline[-20:]:
            loc = comment.path or ""
            if comment.line is not None:
                loc = f"{loc}:{comment.line}"
            lines.append("")
            lines.append(f"### {loc} — {comment.author}".strip(" —"))
            lines.append(truncate(comment.body, 1500))

    if reviews or discussion:
        lines.append("")
        lines.append("## Discussion")
        recent = events[-12:]
        for comment in recent:
            lines.append("")
            kind = "Review" if comment.kind == "review" else "Comment"
            lines.append(f"### {kind} — {comment.author}")
            lines.append(truncate(comment.body, 1500))

    if brief.checks:
        lines.append("")
        lines.append("## Checks")
        for check in brief.checks[:30]:
            detail = f" — {check.details}" if check.details else ""
            lines.append(f"- {check.name}: {check.status}{detail}")

    lines.append("")
    lines.append("## Ending")
    ending = ending_text(brief)
    lines.append(ending)

    lines.append("")
    lines.append("## Resume instruction")
    lines.append(
        "Continue the interrupted work from this brief. "
        "Do not summarise and wait. Ground against the live workspace, then act."
    )
    return "\n".join(lines) + "\n"


def ending_text(brief: Brief) -> str:
    events = chronological_events(brief.comments)
    requested = [
        c
        for c in events
        if c.kind == "review" and "CHANGES_REQUESTED" in (c.body or "").upper()
    ]
    if brief.review_decision:
        decision = brief.review_decision.replace("_", " ").title()
        if requested:
            return truncate(
                f"{decision}. {requested[-1].author}: {requested[-1].body}", 800
            )
        return decision
    failing = [
        c
        for c in brief.checks
        if c.status.upper() in {"FAILURE", "FAILED", "CANCELLED", "ERROR", "ACTION_REQUIRED"}
    ]
    if failing:
        names = ", ".join(c.name for c in failing[:5])
        return f"Failing checks: {names}"
    last = next(
        (c for c in reversed(events) if (c.body or "").strip()),
        None,
    )
    if last:
        return truncate(f"{last.author}: {last.body}", 800)
    if brief.draft:
        return "Draft — work still in flight."
    if brief.commits:
        return truncate(brief.commits[-1], 400)
    return "(no clear ending text — pick up from the PR goal and files in play)"


# ---------------------------------------------------------------------------
# HTTP / CLI
# ---------------------------------------------------------------------------

USER_AGENT = "jonbaldie-skills-resume-from-pr"


def env_token(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def http_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    request = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise FetchError(f"HTTP {exc.code} for {url}: {truncate(body, 240)}") from exc
    except urllib.error.URLError as exc:
        raise Skip(f"network error for {url}: {exc.reason}") from exc
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FetchError(f"Non-JSON response from {url}") from exc


def run_cmd(
    argv: list[str],
    cwd: str | None = None,
    timeout: int = 45,
) -> str:
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise Skip(f"{argv[0]} not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise Skip(f"{argv[0]} timed out") from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise Skip(f"{argv[0]} failed: {truncate(err, 240)}")
    return proc.stdout


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

GH_PR_FIELDS = (
    "title,body,state,author,baseRefName,headRefName,headRefOid,url,number,"
    "isDraft,mergeable,reviewDecision,reviews,comments,commits,files,labels,"
    "statusCheckRollup,closingIssuesReferences,additions,deletions,"
    "changedFiles,headRepositoryOwner,isCrossRepository"
)


def github_api_root(host: str) -> str:
    if host.lower() in {"github.com", "www.github.com"}:
        return "https://api.github.com"
    return f"https://{host}/api/v3"


def github_headers() -> dict[str, str]:
    token = env_token("GH_TOKEN", "GITHUB_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def brief_from_github_view(
    data: dict[str, Any],
    inline: list[dict[str, Any]] | None = None,
    source: str = "gh",
    host: str | None = None,
) -> Brief:
    author = login_of(data.get("author"), "login", "name")
    files = [
        FileChange(
            path=item.get("path") or "",
            additions=item.get("additions"),
            deletions=item.get("deletions"),
            change_type=item.get("changeType") or item.get("status"),
        )
        for item in data.get("files") or []
        if item.get("path")
    ]
    comments: list[Comment] = []
    for review in data.get("reviews") or []:
        body = (review.get("body") or "").strip()
        state = review.get("state") or ""
        text = f"{state}\n{body}".strip() if state else body
        if not text:
            continue
        comments.append(
            Comment(
                author=login_of(review.get("author") or review, "login", "name"),
                body=text,
                created=review.get("submittedAt") or review.get("submitted_at"),
                kind="review",
            )
        )
    for comment in data.get("comments") or []:
        body = (comment.get("body") or "").strip()
        if not body:
            continue
        comments.append(
            Comment(
                author=login_of(comment.get("author") or comment, "login", "name"),
                body=body,
                created=comment.get("createdAt") or comment.get("created_at"),
                kind="discussion",
            )
        )
    for item in inline or []:
        body = (item.get("body") or "").strip()
        if not body:
            continue
        line = item.get("line") or item.get("original_line")
        comments.append(
            Comment(
                author=login_of(item.get("user") or item.get("author"), "login", "name"),
                body=body,
                created=item.get("created_at") or item.get("createdAt"),
                path=item.get("path"),
                line=int(line) if isinstance(line, int) else None,
                kind="inline",
            )
        )
    checks: list[Check] = []
    for item in data.get("statusCheckRollup") or []:
        name = item.get("name") or item.get("context") or "check"
        status = (
            item.get("conclusion")
            or item.get("state")
            or item.get("status")
            or "unknown"
        )
        checks.append(Check(name=name, status=str(status)))
    commits: list[str] = []
    for commit in data.get("commits") or []:
        headline = commit.get("messageHeadline") or commit.get("message") or ""
        oid = (commit.get("oid") or commit.get("sha") or "")[:7]
        if headline:
            commits.append(f"{oid} {headline}".strip())
    labels = []
    for label in data.get("labels") or []:
        if isinstance(label, str):
            labels.append(label)
        elif isinstance(label, dict):
            name = label.get("name")
            if name:
                labels.append(name)
    linked = []
    for issue in data.get("closingIssuesReferences") or []:
        num = issue.get("number")
        title = issue.get("title") or ""
        if num:
            linked.append(f"#{num} {title}".strip())
    repo = None
    url = data.get("url") or ""
    if url:
        try:
            parsed = parse_pr_url(url)
            repo = parsed.slug
            host = host or parsed.host
        except FetchError:
            pass
    return Brief(
        provider="github",
        url=url,
        number=str(data.get("number") or ""),
        title=data.get("title") or "",
        state=(data.get("state") or "").lower(),
        author=author,
        body=data.get("body") or "",
        draft=bool(data.get("isDraft") or data.get("draft")),
        base=data.get("baseRefName") or (data.get("base") or {}).get("ref"),
        head=data.get("headRefName") or (data.get("head") or {}).get("ref"),
        head_sha=data.get("headRefOid")
        or (data.get("head") or {}).get("sha")
        or (data.get("head") or {}).get("oid"),
        repo=repo,
        host=host,
        review_decision=data.get("reviewDecision") or None,
        source=source,
        files=files,
        comments=comments,
        checks=checks,
        commits=commits,
        labels=labels,
        linked_issues=linked,
        fork=bool(data.get("isCrossRepository")),
    )


def brief_from_github_rest(
    pr: dict[str, Any],
    *,
    files: list[dict[str, Any]] | None = None,
    issue_comments: list[dict[str, Any]] | None = None,
    review_comments: list[dict[str, Any]] | None = None,
    reviews: list[dict[str, Any]] | None = None,
    commits: list[dict[str, Any]] | None = None,
    statuses: list[dict[str, Any]] | None = None,
    source: str = "api",
    host: str | None = None,
) -> Brief:
    data: dict[str, Any] = {
        "title": pr.get("title"),
        "body": pr.get("body") or pr.get("description"),
        "state": "merged" if pr.get("merged") else pr.get("state"),
        "author": pr.get("user") or pr.get("author"),
        "baseRefName": (pr.get("base") or {}).get("ref") or pr.get("base_branch"),
        "headRefName": (pr.get("head") or {}).get("ref") or pr.get("head_branch"),
        "headRefOid": (pr.get("head") or {}).get("sha") or pr.get("sha"),
        "url": pr.get("html_url") or pr.get("url"),
        "number": pr.get("number") or pr.get("iid") or pr.get("index"),
        "isDraft": pr.get("draft") or pr.get("isDraft"),
        "reviewDecision": pr.get("reviewDecision"),
        "isCrossRepository": bool(
            (pr.get("head") or {}).get("repo")
            and (pr.get("base") or {}).get("repo")
            and (pr.get("head") or {}).get("repo", {}).get("full_name")
            != (pr.get("base") or {}).get("repo", {}).get("full_name")
        ),
        "labels": pr.get("labels") or [],
        "files": [
            {
                "path": f.get("filename") or f.get("path"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                "changeType": f.get("status"),
            }
            for f in files or []
        ],
        "commits": [
            {
                "messageHeadline": (c.get("commit") or {}).get("message", "").split("\n", 1)[0]
                if isinstance(c.get("commit"), dict)
                else (c.get("title") or c.get("message") or ""),
                "oid": c.get("sha") or (c.get("commit") or {}).get("id"),
            }
            for c in commits or []
        ],
        "comments": issue_comments or [],
        "reviews": [
            {
                "body": r.get("body"),
                "state": r.get("state"),
                "author": r.get("user") or r.get("author"),
                "submittedAt": r.get("submitted_at"),
            }
            for r in reviews or []
        ],
        "statusCheckRollup": [
            {
                "name": s.get("context") or s.get("name") or (s.get("status") or {}).get(
                    "context"
                ),
                "state": s.get("state") or s.get("conclusion") or s.get("status"),
            }
            for s in statuses or []
        ],
    }
    return brief_from_github_view(
        data, inline=review_comments or [], source=source, host=host
    )


def fetch_github_gh(target: Target, cwd: str | None = None) -> Brief:
    locator = target.url or target.number
    argv = ["gh", "pr", "view", locator, "--json", GH_PR_FIELDS]
    if target.slug and not target.url:
        argv.extend(["--repo", target.slug])
    raw = run_cmd(argv, cwd=cwd)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Skip("gh returned non-JSON") from exc
    inline: list[dict[str, Any]] = []
    slug = target.slug
    if slug:
        try:
            comments_raw = run_cmd(
                ["gh", "api", f"repos/{slug}/pulls/{target.number}/comments"],
                cwd=cwd,
            )
            parsed = json.loads(comments_raw)
            if isinstance(parsed, list):
                inline = parsed
        except (Skip, json.JSONDecodeError):
            pass
    return brief_from_github_view(data, inline=inline, source="gh", host=target.host)


def fetch_github_api(target: Target, cwd: str | None = None) -> Brief:
    if not target.slug:
        raise Skip("no owner/repo for GitHub API")
    root = github_api_root(target.host or "github.com")
    base = f"{root}/repos/{target.slug}/pulls/{target.number}"
    headers = github_headers()
    pr = http_json(base, headers=headers)
    if not isinstance(pr, dict):
        raise FetchError(f"No GitHub pull request {target.slug}#{target.number}")

    def get_list(url: str) -> list[dict[str, Any]]:
        try:
            data = http_json(url, headers=headers)
        except (FetchError, Skip):
            return []
        return data if isinstance(data, list) else []

    files = get_list(f"{base}/files")
    review_comments = get_list(f"{base}/comments")
    reviews = get_list(f"{base}/reviews")
    commits = get_list(f"{base}/commits")
    issue_comments = get_list(
        f"{root}/repos/{target.slug}/issues/{target.number}/comments"
    )
    statuses: list[dict[str, Any]] = []
    sha = (pr.get("head") or {}).get("sha")
    if sha:
        status_json = None
        try:
            status_json = http_json(
                f"{root}/repos/{target.slug}/commits/{sha}/status",
                headers=headers,
            )
        except (FetchError, Skip):
            status_json = None
        if isinstance(status_json, dict):
            statuses = status_json.get("statuses") or []
    return brief_from_github_rest(
        pr,
        files=files,
        issue_comments=issue_comments,
        review_comments=review_comments,
        reviews=reviews,
        commits=commits,
        statuses=statuses,
        source="api",
        host=target.host,
    )


# ---------------------------------------------------------------------------
# GitLab
# ---------------------------------------------------------------------------


def gitlab_headers() -> dict[str, str]:
    token = env_token("GITLAB_TOKEN", "GL_TOKEN", "PRIVATE_TOKEN")
    if token:
        return {"PRIVATE-TOKEN": token}
    return {}


def gitlab_project_id(target: Target) -> str:
    path = target.project or target.slug or ""
    return urllib.parse.quote(path, safe="")


def brief_from_gitlab(
    mr: dict[str, Any],
    *,
    changes: list[dict[str, Any]] | None = None,
    discussions: list[dict[str, Any]] | None = None,
    commits: list[dict[str, Any]] | None = None,
    source: str = "api",
    host: str | None = None,
) -> Brief:
    files: list[FileChange] = []
    for change in changes or mr.get("changes") or []:
        path = change.get("new_path") or change.get("old_path") or change.get("path")
        if path:
            files.append(FileChange(path=path, change_type="deleted" if change.get("deleted_file") else None))
    comments: list[Comment] = []
    for discussion in discussions or []:
        for note in discussion.get("notes") or []:
            if note.get("system"):
                continue
            body = (note.get("body") or "").strip()
            if not body:
                continue
            position = note.get("position") or {}
            path = position.get("new_path") or position.get("old_path")
            line = position.get("new_line") or position.get("old_line")
            kind = "inline" if path else "discussion"
            comments.append(
                Comment(
                    author=login_of(note.get("author"), "username", "name"),
                    body=body,
                    created=note.get("created_at"),
                    path=path,
                    line=int(line) if isinstance(line, int) else None,
                    kind=kind,
                )
            )
    commit_lines = []
    for commit in commits or []:
        title = commit.get("title") or (commit.get("message") or "").split("\n", 1)[0]
        oid = (commit.get("id") or commit.get("short_id") or "")[:7]
        if title:
            commit_lines.append(f"{oid} {title}".strip())
    pipeline = mr.get("head_pipeline") or mr.get("pipeline") or {}
    checks = []
    if pipeline:
        checks.append(
            Check(
                name="pipeline",
                status=str(pipeline.get("status") or "unknown"),
                details=pipeline.get("web_url"),
            )
        )
    labels = [str(x) for x in (mr.get("labels") or [])]
    diff_refs = mr.get("diff_refs") if isinstance(mr.get("diff_refs"), dict) else {}
    return Brief(
        provider="gitlab",
        url=mr.get("web_url") or mr.get("url") or "",
        number=str(mr.get("iid") or mr.get("id") or ""),
        title=mr.get("title") or "",
        state=(mr.get("state") or "").lower(),
        author=login_of(mr.get("author"), "username", "name"),
        body=mr.get("description") or "",
        draft=bool(mr.get("draft") or mr.get("work_in_progress")),
        base=mr.get("target_branch"),
        head=mr.get("source_branch"),
        head_sha=mr.get("sha") or diff_refs.get("head_sha"),
        repo=mr.get("references", {}).get("full")
        if isinstance(mr.get("references"), dict)
        else None,
        host=host,
        source=source,
        files=files,
        comments=comments,
        checks=checks,
        commits=commit_lines,
        labels=labels,
        fork=bool(mr.get("source_project_id") and mr.get("target_project_id") and mr.get("source_project_id") != mr.get("target_project_id")),
    )


def fetch_gitlab_glab(target: Target, cwd: str | None = None) -> Brief:
    locator = target.url or target.number
    raw = run_cmd(["glab", "mr", "view", locator, "--output", "json", "--comments"], cwd=cwd)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Skip("glab returned non-JSON") from exc
    if isinstance(data, list):
        data = data[0] if data else {}
    return brief_from_gitlab(data, source="glab", host=target.host)


def fetch_gitlab_api(target: Target, cwd: str | None = None) -> Brief:
    project = gitlab_project_id(target)
    if not project:
        raise Skip("no GitLab project path")
    host = target.host or "gitlab.com"
    root = f"https://{host}/api/v4/projects/{project}/merge_requests/{target.number}"
    headers = gitlab_headers()
    mr = http_json(root, headers=headers)
    if not isinstance(mr, dict):
        raise FetchError(f"No GitLab merge request {target.slug}!{target.number}")

    def get_list(url: str) -> list[dict[str, Any]]:
        try:
            data = http_json(url, headers=headers)
        except (FetchError, Skip):
            return []
        return data if isinstance(data, list) else []

    changes_json: Any = None
    try:
        changes_json = http_json(f"{root}/changes", headers=headers)
    except (FetchError, Skip):
        changes_json = None
    changes = []
    if isinstance(changes_json, dict):
        changes = changes_json.get("changes") or []
    elif isinstance(changes_json, list):
        changes = changes_json
    discussions = get_list(f"{root}/discussions")
    commits = get_list(f"{root}/commits")
    return brief_from_gitlab(
        mr,
        changes=changes,
        discussions=discussions,
        commits=commits,
        source="api",
        host=host,
    )


# ---------------------------------------------------------------------------
# Bitbucket
# ---------------------------------------------------------------------------


def bitbucket_headers() -> dict[str, str]:
    token = env_token("BITBUCKET_TOKEN", "BITBUCKET_ACCESS_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    user = os.environ.get("BITBUCKET_USERNAME")
    password = env_token("BITBUCKET_APP_PASSWORD", "BITBUCKET_PASSWORD")
    if user and password:
        cred = f"{user}:{password}"
        encoded = base64.b64encode(cred.encode()).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    return {}


def brief_from_bitbucket(
    pr: dict[str, Any],
    *,
    comments: list[dict[str, Any]] | None = None,
    diffstat: list[dict[str, Any]] | None = None,
    statuses: list[dict[str, Any]] | None = None,
    source: str = "api",
    host: str | None = None,
) -> Brief:
    src = pr.get("source") or {}
    dest = pr.get("destination") or {}
    files = []
    for item in diffstat or []:
        new = ((item.get("new") or {}).get("path")) or ((item.get("old") or {}).get("path"))
        if new:
            files.append(
                FileChange(
                    path=new,
                    change_type=item.get("status"),
                    additions=item.get("lines_added"),
                    deletions=item.get("lines_removed"),
                )
            )
    parsed_comments: list[Comment] = []
    for item in comments or []:
        body = ((item.get("content") or {}).get("raw")) or item.get("raw") or ""
        body = body.strip()
        if not body:
            continue
        inline = item.get("inline") or {}
        path = inline.get("path")
        line = inline.get("to") or inline.get("from")
        parsed_comments.append(
            Comment(
                author=login_of(item.get("user"), "display_name", "nickname", "name"),
                body=body,
                created=item.get("created_on"),
                path=path,
                line=int(line) if isinstance(line, int) else None,
                kind="inline" if path else "discussion",
            )
        )
    checks = []
    for item in statuses or []:
        checks.append(
            Check(
                name=item.get("name") or item.get("key") or "status",
                status=str(item.get("state") or "unknown"),
            )
        )
    links = pr.get("links") or {}
    html = (links.get("html") or {}).get("href") or pr.get("url") or ""
    return Brief(
        provider="bitbucket",
        url=html,
        number=str(pr.get("id") or ""),
        title=pr.get("title") or "",
        state=(pr.get("state") or "").lower(),
        author=login_of(pr.get("author"), "display_name", "nickname"),
        body=pr.get("description") or "",
        draft=bool(pr.get("draft")),
        base=(dest.get("branch") or {}).get("name"),
        head=(src.get("branch") or {}).get("name"),
        head_sha=(src.get("commit") or {}).get("hash"),
        repo=f"{(pr.get('destination') or {}).get('repository', {}).get('full_name')}" if isinstance((pr.get("destination") or {}).get("repository"), dict) else None,
        host=host,
        source=source,
        files=files,
        comments=parsed_comments,
        checks=checks,
    )


def fetch_bitbucket_api(target: Target, cwd: str | None = None) -> Brief:
    if not target.slug:
        raise Skip("no workspace/repo for Bitbucket API")
    host = (target.host or "bitbucket.org").lower()
    if host in {"bitbucket.org", "www.bitbucket.org"}:
        root = f"https://api.bitbucket.org/2.0/repositories/{target.slug}/pullrequests/{target.number}"
    else:
        raise Skip("Bitbucket Server uses a different API path")
    headers = bitbucket_headers()
    pr = http_json(root, headers=headers)
    if not isinstance(pr, dict):
        raise FetchError(f"No Bitbucket pull request {target.slug}#{target.number}")

    def values(url: str) -> list[dict[str, Any]]:
        try:
            data = http_json(url, headers=headers)
        except (FetchError, Skip):
            return []
        if isinstance(data, dict):
            return data.get("values") or []
        return data if isinstance(data, list) else []

    comments = values(f"{root}/comments")
    diffstat = values(f"{root}/diffstat")
    statuses = values(f"{root}/statuses")
    return brief_from_bitbucket(
        pr,
        comments=comments,
        diffstat=diffstat,
        statuses=statuses,
        source="api",
        host=target.host,
    )


def fetch_bitbucket_server_api(target: Target, cwd: str | None = None) -> Brief:
    if not target.owner or not target.repo:
        raise Skip("no project/repo for Bitbucket Server")
    root = (
        f"https://{target.host}/rest/api/1.0/projects/{target.owner}"
        f"/repos/{target.repo}/pull-requests/{target.number}"
    )
    headers = bitbucket_headers()
    pr = http_json(root, headers=headers)
    if not isinstance(pr, dict):
        raise FetchError(f"No Bitbucket Server pull request {target.number}")
    from_ref = pr.get("fromRef") or {}
    to_ref = pr.get("toRef") or {}
    files: list[FileChange] = []
    try:
        changes = http_json(f"{root}/changes?limit=50", headers=headers)
        for item in (changes or {}).get("values") or []:
            path = ((item.get("path") or {}).get("toString")) or ""
            if path:
                files.append(FileChange(path=path, change_type=item.get("type")))
    except (FetchError, Skip):
        pass
    comments: list[Comment] = []
    try:
        activities = http_json(f"{root}/activities?limit=50", headers=headers)
        for item in (activities or {}).get("values") or []:
            comment = item.get("comment") or {}
            body = (comment.get("text") or "").strip()
            if not body:
                continue
            comments.append(
                Comment(
                    author=login_of(comment.get("author"), "name", "displayName"),
                    body=body,
                    created=str(comment.get("createdDate") or ""),
                    kind="discussion",
                )
            )
    except (FetchError, Skip):
        pass
    return Brief(
        provider="bitbucket-server",
        url=target.url or "",
        number=str(pr.get("id") or target.number),
        title=pr.get("title") or "",
        state=(pr.get("state") or "").lower(),
        author=login_of(pr.get("author"), "name", "displayName"),
        body=pr.get("description") or "",
        draft=bool(pr.get("draft")),
        base=to_ref.get("displayId"),
        head=from_ref.get("displayId"),
        head_sha=from_ref.get("latestCommit"),
        repo=f"{target.owner}/{target.repo}",
        host=target.host,
        source="api",
        files=files,
        comments=comments,
    )


# ---------------------------------------------------------------------------
# Gitea / Forgejo
# ---------------------------------------------------------------------------


def gitea_headers() -> dict[str, str]:
    token = env_token("GITEA_TOKEN", "FORGEJO_TOKEN", "CODEBERG_TOKEN")
    if token:
        return {"Authorization": f"token {token}"}
    return {}


def fetch_gitea_api(target: Target, cwd: str | None = None) -> Brief:
    if not target.slug:
        raise Skip("no owner/repo for Gitea API")
    host = target.host
    root = f"https://{host}/api/v1/repos/{target.slug}/pulls/{target.number}"
    headers = gitea_headers()
    pr = http_json(root, headers=headers)
    if not isinstance(pr, dict):
        raise FetchError(f"No Gitea pull request {target.slug}#{target.number}")

    def get_list(url: str) -> list[dict[str, Any]]:
        try:
            data = http_json(url, headers=headers)
        except (FetchError, Skip):
            return []
        return data if isinstance(data, list) else []

    files = get_list(f"{root}/files")
    reviews = get_list(f"{root}/reviews")
    issue_comments = get_list(
        f"https://{host}/api/v1/repos/{target.slug}/issues/{target.number}/comments"
    )
    return brief_from_github_rest(
        pr,
        files=files,
        issue_comments=issue_comments,
        reviews=reviews,
        source="api",
        host=host,
    )


# ---------------------------------------------------------------------------
# Azure DevOps
# ---------------------------------------------------------------------------


def azure_headers() -> dict[str, str]:
    token = env_token("AZURE_DEVOPS_TOKEN", "SYSTEM_ACCESSTOKEN", "AZURE_TOKEN")
    if not token:
        return {}
    encoded = base64.b64encode(f":{token}".encode()).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def brief_from_azure(
    pr: dict[str, Any],
    *,
    threads: list[dict[str, Any]] | None = None,
    statuses: list[dict[str, Any]] | None = None,
    source: str = "api",
    target: Target | None = None,
) -> Brief:
    comments: list[Comment] = []
    for thread in threads or []:
        for item in thread.get("comments") or []:
            if item.get("commentType") == "system":
                continue
            body = (item.get("content") or "").strip()
            if not body:
                continue
            ctx = thread.get("threadContext") or {}
            path = ctx.get("filePath")
            line = (ctx.get("rightFileEnd") or {}).get("line") or (
                ctx.get("rightFileStart") or {}
            ).get("line")
            comments.append(
                Comment(
                    author=login_of(
                        item.get("author"), "displayName", "uniqueName", "name"
                    ),
                    body=body,
                    created=item.get("publishedDate"),
                    path=path.lstrip("/") if isinstance(path, str) else path,
                    line=int(line) if isinstance(line, int) else None,
                    kind="inline" if path else "discussion",
                )
            )
    checks = []
    for item in statuses or []:
        checks.append(
            Check(
                name=item.get("context", {}).get("name")
                if isinstance(item.get("context"), dict)
                else item.get("description") or "status",
                status=str(item.get("state") or "unknown"),
            )
        )
    repo = (pr.get("repository") or {}).get("name")
    url = ""
    if target and target.url:
        url = target.url
    elif target:
        url = (
            f"https://dev.azure.com/{target.org}/{target.project}/_git/"
            f"{target.repo}/pullrequest/{target.number}"
        )
    return Brief(
        provider="azure",
        url=url,
        number=str(pr.get("pullRequestId") or ""),
        title=pr.get("title") or "",
        state=(pr.get("status") or "").lower(),
        author=login_of(pr.get("createdBy"), "displayName", "uniqueName"),
        body=pr.get("description") or "",
        draft=bool(pr.get("isDraft")),
        base=(pr.get("targetRefName") or "").removeprefix("refs/heads/"),
        head=(pr.get("sourceRefName") or "").removeprefix("refs/heads/"),
        head_sha=(pr.get("lastMergeSourceCommit") or {}).get("commitId")
        or (pr.get("lastMergeCommit") or {}).get("commitId"),
        repo=repo,
        host=target.host if target else None,
        source=source,
        comments=comments,
        checks=checks,
    )


def fetch_azure_api(target: Target, cwd: str | None = None) -> Brief:
    if not (target.org and target.project and target.repo):
        raise Skip("incomplete Azure DevOps target")
    org = urllib.parse.quote(target.org)
    project = urllib.parse.quote(target.project)
    repo = urllib.parse.quote(target.repo)
    root = (
        f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}"
        f"/pullrequests/{target.number}"
    )
    headers = azure_headers()
    pr = http_json(f"{root}?api-version=7.1", headers=headers)
    if not isinstance(pr, dict):
        raise FetchError(f"No Azure DevOps pull request {target.number}")
    threads: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    try:
        thread_json = http_json(f"{root}/threads?api-version=7.1", headers=headers)
        if isinstance(thread_json, dict):
            threads = thread_json.get("value") or []
    except (FetchError, Skip):
        pass
    try:
        status_json = http_json(f"{root}/statuses?api-version=7.1", headers=headers)
        if isinstance(status_json, dict):
            statuses = status_json.get("value") or []
    except (FetchError, Skip):
        pass
    return brief_from_azure(
        pr, threads=threads, statuses=statuses, source="api", target=target
    )


# ---------------------------------------------------------------------------
# Git fallback
# ---------------------------------------------------------------------------

PR_REF_PATTERNS = (
    "refs/pull/{n}/head",
    "refs/pull/{n}/merge",
    "refs/merge-requests/{n}/head",
    "refs/pulls/{n}/head",
    "refs/pull-requests/{n}/from",
    "refs/pull-requests/{n}/head",
)


def git_remotes(cwd: str) -> list[tuple[str, str]]:
    try:
        raw = run_cmd(["git", "remote", "-v"], cwd=cwd)
    except Skip:
        return []
    seen: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        if name not in seen:
            seen[name] = url
    # Prefer origin, then upstream.
    ordered = []
    for name in ("origin", "upstream"):
        if name in seen:
            ordered.append((name, seen.pop(name)))
    ordered.extend(seen.items())
    return ordered


def target_from_remote(number: str, remote_url: str) -> Target | None:
    try:
        host, path = parse_git_remote(remote_url)
    except FetchError:
        return None
    path = path.rstrip("/")
    owner, repo = split_path(path)
    host_l = host.lower()
    if host_l in {"github.com", "www.github.com"}:
        return Target(
            provider="github",
            host="github.com",
            number=number,
            owner=owner,
            repo=repo,
            url=f"https://github.com/{owner}/{repo}/pull/{number}",
        )
    if host_l in {"gitlab.com", "www.gitlab.com"} or "gitlab" in host_l:
        return Target(
            provider="gitlab",
            host=host,
            number=number,
            owner=owner,
            repo=repo,
            project=path,
            url=f"https://{host}/{path}/-/merge_requests/{number}",
        )
    if host_l in {"bitbucket.org", "www.bitbucket.org"}:
        return Target(
            provider="bitbucket",
            host="bitbucket.org",
            number=number,
            owner=owner,
            repo=repo,
            url=f"https://bitbucket.org/{owner}/{repo}/pull-requests/{number}",
        )
    if host_l in {"dev.azure.com", "ssh.dev.azure.com"} or host_l.endswith(
        ".visualstudio.com"
    ):
        return _azure_remote_target(host, path, number)
    if host_l in {"codeberg.org", "gitea.com"} or "gitea" in host_l or "forgejo" in host_l:
        return Target(
            provider="gitea",
            host=host,
            number=number,
            owner=owner,
            repo=repo,
            url=f"https://{host}/{owner}/{repo}/pulls/{number}",
        )
    m = _BITBUCKET_SERVER_REMOTE.match(path)
    if m:
        key = m.group("key") or m.group("key2")
        slug = m.group("slug") or m.group("slug2")
        return Target(
            provider="bitbucket-server",
            host=host,
            number=number,
            owner=key,
            repo=slug,
            url=f"https://{host}/projects/{key}/repos/{slug}/pull-requests/{number}",
        )
    return Target(
        provider="unknown",
        host=host,
        number=number,
        owner=owner,
        repo=repo,
    )


def _azure_remote_target(host: str, path: str, number: str) -> Target | None:
    """Build an Azure DevOps target from a git remote host and path."""
    host_l = host.lower()
    if host_l == "ssh.dev.azure.com":
        m = _AZURE_REMOTE_SSH.match(path)
        if not m:
            return None
        org = m.group("org")
        project = m.group("project")
        repo = m.group("repo")
    elif host_l.endswith(".visualstudio.com"):
        org = host.split(".", 1)[0]
        path = urllib.parse.unquote(re.sub(r"^DefaultCollection/", "", path, flags=re.I))
        m = _AZURE_REMOTE_VS.match(path)
        if not m:
            return None
        project = m.group("project") or org
        repo = m.group("repo")
    else:
        path = urllib.parse.unquote(path)
        m = _AZURE_REMOTE_HTTPS.match(path)
        if m:
            org = m.group("org")
            project = m.group("project")
            repo = m.group("repo")
        else:
            m = _AZURE_REMOTE_SHORT.match(path)
            if not m:
                return None
            org = m.group("org")
            project = org  # project defaults to the organisation name
            repo = m.group("repo")
    return Target(
        provider="azure",
        host=host,
        number=number,
        owner=org,
        repo=repo,
        project=project,
        org=org,
        url=(
            f"https://dev.azure.com/{urllib.parse.quote(org)}/"
            f"{urllib.parse.quote(project)}/_git/{urllib.parse.quote(repo)}"
            f"/pullrequest/{number}"
        ),
    )


def fetch_git(target: Target, cwd: str | None) -> Brief:
    if not cwd:
        raise Skip("no cwd for git fallback")
    remotes = git_remotes(cwd)
    if not remotes:
        raise Skip("not a git repository")
    last_err = "no matching PR ref"
    for name, url in remotes:
        try:
            listing = run_cmd(["git", "ls-remote", name], cwd=cwd, timeout=30)
        except Skip as exc:
            last_err = str(exc)
            continue
        wanted = {pat.format(n=target.number) for pat in PR_REF_PATTERNS}
        hit = None
        for line in listing.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            sha, ref = parts[0], parts[1]
            if ref in wanted:
                hit = (sha, ref)
                if ref.endswith("/head") or ref.endswith("/from"):
                    break
        if not hit:
            continue
        sha, ref = hit
        try:
            run_cmd(
                ["git", "fetch", "--quiet", name, f"{ref}:refs/resume-from-pr/{target.number}"],
                cwd=cwd,
            )
            local = f"refs/resume-from-pr/{target.number}"
        except Skip:
            local = sha
        files: list[FileChange] = []
        commits: list[str] = []
        title = f"PR/MR {target.number}"
        body = ""
        try:
            log = run_cmd(
                ["git", "log", "--format=%h %s", "-15", local],
                cwd=cwd,
            )
            commits = [line for line in log.splitlines() if line.strip()]
            if commits:
                title = commits[0].split(" ", 1)[-1]
        except Skip:
            pass
        try:
            msg = run_cmd(["git", "log", "-1", "--format=%B", local], cwd=cwd)
            body = msg.strip()
        except Skip:
            pass
        try:
            stat = run_cmd(
                ["git", "diff", "--numstat", f"{name}/HEAD...{local}"],
                cwd=cwd,
            )
            for line in stat.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    add, delete, path = parts[0], parts[1], parts[2]
                    files.append(
                        FileChange(
                            path=path,
                            additions=int(add) if add.isdigit() else None,
                            deletions=int(delete) if delete.isdigit() else None,
                        )
                    )
        except Skip:
            pass
        return Brief(
            provider=target.provider if target.provider != "unknown" else "git",
            url=target.url or f"{url} {ref}",
            number=target.number,
            title=title,
            state="open",
            author="",
            body=body,
            head_sha=sha,
            repo=target.slug,
            host=target.host,
            source="git",
            files=files,
            commits=commits,
        )
    raise Skip(last_err)


# ---------------------------------------------------------------------------
# Resolve + dispatch
# ---------------------------------------------------------------------------

FETCHERS: dict[str, list[Callable[[Target, str | None], Brief]]] = {
    "github": [fetch_github_gh, fetch_github_api, fetch_git],
    "gitlab": [fetch_gitlab_glab, fetch_gitlab_api, fetch_git],
    "bitbucket": [fetch_bitbucket_api, fetch_git],
    "bitbucket-server": [fetch_bitbucket_server_api, fetch_git],
    "gitea": [fetch_gitea_api, fetch_git],
    "azure": [fetch_azure_api, fetch_git],
    "unknown": [
        fetch_github_gh,
        fetch_github_api,
        fetch_gitlab_glab,
        fetch_gitlab_api,
        fetch_gitea_api,
        fetch_git,
    ],
}


def git_current_branch(cwd: str) -> str | None:
    try:
        raw = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    except Skip:
        return None
    branch = raw.strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def _gh_cli_branch_target(cwd: str) -> Target:
    raw = run_cmd(["gh", "pr", "view", "--json", "url"], cwd=cwd)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Skip("gh returned non-JSON") from exc
    url = data.get("url")
    if not url:
        raise Skip("gh returned no pull request url")
    return parse_pr_url(url)


def _glab_cli_branch_target(cwd: str) -> Target:
    raw = run_cmd(["glab", "mr", "view", "--output", "json"], cwd=cwd)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Skip("glab returned non-JSON") from exc
    if isinstance(data, list):
        data = data[0] if data else {}
    url = data.get("web_url") or data.get("url")
    if url:
        return parse_pr_url(url)
    iid = data.get("iid")
    if iid:
        return Target(provider="gitlab", host="gitlab.com", number=str(iid))
    raise Skip("glab returned no merge request")


def github_branch_target(remote: Target, branch: str) -> Target:
    if not remote.slug:
        raise Skip("no owner/repo for GitHub API")
    root = f"{github_api_root(remote.host or 'github.com')}/repos/{remote.slug}/pulls"
    query = f"?head={urllib.parse.quote(f'{remote.owner}:{branch}', safe='')}&state=open"
    try:
        data = http_json(root + query, headers=github_headers())
    except Skip as exc:
        raise _branch_lookup_failure("github", remote, branch, f"network error: {exc}") from exc
    except FetchError as exc:
        raise _branch_lookup_failure("github", remote, branch, str(exc)) from exc
    prs = data if isinstance(data, list) else []
    pr = next((p for p in prs if isinstance(p, dict)), None)
    if not pr:
        raise _branch_lookup_empty("github", remote, branch)
    return Target(
        provider="github",
        host=remote.host or "github.com",
        number=str(pr.get("number") or ""),
        owner=remote.owner,
        repo=remote.repo,
        url=pr.get("html_url") or "",
    )


def gitlab_branch_target(remote: Target, branch: str) -> Target:
    project = gitlab_project_id(remote)
    if not project:
        raise Skip("no GitLab project path")
    host = remote.host or "gitlab.com"
    query = f"?source_branch={urllib.parse.quote(branch, safe='')}&state=opened"
    root = f"https://{host}/api/v4/projects/{project}/merge_requests{query}"
    try:
        data = http_json(root, headers=gitlab_headers())
    except Skip as exc:
        raise _branch_lookup_failure("gitlab", remote, branch, f"network error: {exc}") from exc
    except FetchError as exc:
        raise _branch_lookup_failure("gitlab", remote, branch, str(exc)) from exc
    mrs = data if isinstance(data, list) else []
    mr = next((m for m in mrs if isinstance(m, dict)), None)
    if not mr:
        raise _branch_lookup_empty("gitlab", remote, branch)
    return Target(
        provider="gitlab",
        host=remote.host,
        number=str(mr.get("iid") or ""),
        owner=remote.owner,
        repo=remote.repo,
        project=remote.project,
        url=mr.get("web_url") or "",
    )


def bitbucket_branch_target(remote: Target, branch: str) -> Target:
    if not remote.slug:
        raise Skip("no workspace/repo for Bitbucket API")
    q = f'source.branch.name="{branch}" AND state="OPEN"'
    root = (
        f"https://api.bitbucket.org/2.0/repositories/{remote.slug}"
        f"/pullrequests?q={urllib.parse.quote(q, safe='')}"
    )
    try:
        data = http_json(root, headers=bitbucket_headers())
    except Skip as exc:
        raise _branch_lookup_failure("bitbucket", remote, branch, f"network error: {exc}") from exc
    except FetchError as exc:
        raise _branch_lookup_failure("bitbucket", remote, branch, str(exc)) from exc
    values = data.get("values") or [] if isinstance(data, dict) else []
    pr = next((p for p in values if isinstance(p, dict)), None)
    if not pr:
        raise _branch_lookup_empty("bitbucket", remote, branch)
    href = ((pr.get("links") or {}).get("html") or {}).get("href") or ""
    return Target(
        provider="bitbucket",
        host=remote.host or "bitbucket.org",
        number=str(pr.get("id") or ""),
        owner=remote.owner,
        repo=remote.repo,
        url=href,
    )


def bitbucket_server_branch_target(remote: Target, branch: str) -> Target:
    if not (remote.owner and remote.repo):
        raise Skip("no project/repo for Bitbucket Server")
    query = (
        f"?at={urllib.parse.quote('refs/heads/' + branch, safe='')}"
        "&direction=outgoing&state=OPEN"
    )
    root = (
        f"https://{remote.host}/rest/api/1.0/projects/{remote.owner}"
        f"/repos/{remote.repo}/pull-requests{query}"
    )
    try:
        data = http_json(root, headers=bitbucket_headers())
    except Skip as exc:
        raise _branch_lookup_failure(
            "bitbucket-server", remote, branch, f"network error: {exc}"
        ) from exc
    except FetchError as exc:
        raise _branch_lookup_failure("bitbucket-server", remote, branch, str(exc)) from exc
    values = data.get("values") or [] if isinstance(data, dict) else []
    pr = next((p for p in values if isinstance(p, dict)), None)
    if not pr:
        raise _branch_lookup_empty("bitbucket-server", remote, branch)
    number = str(pr.get("id") or "")
    return Target(
        provider="bitbucket-server",
        host=remote.host,
        number=number,
        owner=remote.owner,
        repo=remote.repo,
        url=(
            f"https://{remote.host}/projects/{remote.owner}/repos/{remote.repo}"
            f"/pull-requests/{number}"
        ),
    )


def gitea_branch_target(remote: Target, branch: str) -> Target:
    if not remote.slug:
        raise Skip("no owner/repo for Gitea API")
    host = remote.host
    root = f"https://{host}/api/v1/repos/{remote.slug}/pulls?state=open"
    try:
        data = http_json(root, headers=gitea_headers())
    except Skip as exc:
        raise _branch_lookup_failure("gitea", remote, branch, f"network error: {exc}") from exc
    except FetchError as exc:
        raise _branch_lookup_failure("gitea", remote, branch, str(exc)) from exc
    prs = data if isinstance(data, list) else []
    same_repo = fork = None
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        head = pr.get("head") or {}
        if head.get("ref") != branch:
            continue
        if ((head.get("repo") or {}).get("full_name") or "").lower() == (
            remote.slug or ""
        ).lower():
            same_repo = same_repo or pr
        else:
            fork = fork or pr
    pr = same_repo or fork
    if not pr:
        raise _branch_lookup_empty("gitea", remote, branch)
    return Target(
        provider="gitea",
        host=host,
        number=str(pr.get("number") or pr.get("id") or ""),
        owner=remote.owner,
        repo=remote.repo,
        url=pr.get("html_url") or "",
    )


def azure_branch_target(remote: Target, branch: str) -> Target:
    if not (remote.org and remote.project and remote.repo):
        raise _branch_lookup_failure(
            "azure",
            remote,
            branch,
            "could not parse org/project/repo from the git remote "
            f"({remote.url or remote.host})",
        )
    org = urllib.parse.quote(remote.org)
    project = urllib.parse.quote(remote.project)
    repo = urllib.parse.quote(remote.repo)
    root = (
        f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}"
        "/pullrequests"
    )
    query = (
        f"?searchCriteria.sourceRefName="
        f"{urllib.parse.quote('refs/heads/' + branch, safe='')}"
        "&searchCriteria.status=active&api-version=7.1"
    )
    try:
        data = http_json(root + query, headers=azure_headers())
    except Skip as exc:
        raise _branch_lookup_failure("azure", remote, branch, f"network error: {exc}") from exc
    except FetchError as exc:
        raise _branch_lookup_failure("azure", remote, branch, str(exc)) from exc
    values = data.get("value") or [] if isinstance(data, dict) else []
    pr = next((p for p in values if isinstance(p, dict)), None)
    if not pr:
        raise _branch_lookup_empty("azure", remote, branch)
    number = str(pr.get("pullRequestId") or "")
    repository = pr.get("repository") or {}
    repo_name = repository.get("name") or remote.repo
    project_name = (repository.get("project") or {}).get("name") or remote.project
    return Target(
        provider="azure",
        host=remote.host,
        number=number,
        owner=remote.org,
        repo=repo_name,
        project=project_name,
        org=remote.org,
        url=(
            f"https://dev.azure.com/{org}/{urllib.parse.quote(project_name)}"
            f"/_git/{urllib.parse.quote(repo_name)}/pullrequest/{number}"
        ),
    )


PROVIDER_LABELS = {
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
    "bitbucket-server": "Bitbucket Server",
    "gitea": "Gitea/Forgejo",
    "azure": "Azure DevOps",
}

PROVIDER_TOKEN_HINTS = {
    "github": "for private repositories set GH_TOKEN or GITHUB_TOKEN",
    "gitlab": "for private projects set GITLAB_TOKEN, GL_TOKEN, or PRIVATE_TOKEN",
    "bitbucket": "for private repositories set BITBUCKET_TOKEN, "
    "BITBUCKET_ACCESS_TOKEN, or BITBUCKET_USERNAME with BITBUCKET_APP_PASSWORD",
    "bitbucket-server": "for private servers set BITBUCKET_TOKEN or "
    "BITBUCKET_ACCESS_TOKEN",
    "gitea": "for private instances set GITEA_TOKEN, FORGEJO_TOKEN, or CODEBERG_TOKEN",
    "azure": "for private projects set AZURE_DEVOPS_TOKEN, SYSTEM_ACCESSTOKEN, "
    "or AZURE_TOKEN",
}


def _branch_lookup_failure(
    provider: str, remote: Target, branch: str, detail: str
) -> FetchError:
    label = PROVIDER_LABELS.get(provider, provider)
    message = (
        f"{label}: could not look up the open pull request for branch "
        f"'{branch}' on {remote.host or label}: {detail}"
    )
    hint = PROVIDER_TOKEN_HINTS.get(provider)
    if hint:
        message += f" ({hint})"
    return FetchError(message)


def _branch_lookup_empty(provider: str, remote: Target, branch: str) -> FetchError:
    label = PROVIDER_LABELS.get(provider, provider)
    return FetchError(
        f"{label}: no open pull request for branch '{branch}' on "
        f"{remote.host or label}. Pass a PR/MR URL."
    )


# Provider-appropriate lookups for the no-argument current-branch mode.
BRANCH_LOOKUPS: dict[str, Callable[[Target, str], Target]] = {
    "github": github_branch_target,
    "gitlab": gitlab_branch_target,
    "bitbucket": bitbucket_branch_target,
    "bitbucket-server": bitbucket_server_branch_target,
    "gitea": gitea_branch_target,
    "azure": azure_branch_target,
}

# CLI helpers preferred where the provider ships one.
CLI_LOOKUPS: dict[str, Callable[[str], Target]] = {
    "github": _gh_cli_branch_target,
    "gitlab": _glab_cli_branch_target,
}


def resolve_current_branch(cwd: str) -> Target:
    branch = git_current_branch(cwd)
    remotes = git_remotes(cwd)
    remote = None
    for _, url in remotes:
        candidate = target_from_remote("0", url)
        if candidate and candidate.provider != "unknown":
            remote = candidate
            break
    if remote is not None and remote.provider != "unknown":
        label = PROVIDER_LABELS.get(remote.provider, remote.provider)
        if not branch:
            raise FetchError(
                f"{label}: cannot find the current-branch pull request because this "
                "workspace has no current branch (detached HEAD?). Pass a PR/MR URL."
            )
        errors: list[str] = []
        cli_lookup = CLI_LOOKUPS.get(remote.provider)
        if cli_lookup:
            try:
                return cli_lookup(cwd)
            except (Skip, FetchError) as exc:
                errors.append(str(exc))
        api_lookup = BRANCH_LOOKUPS.get(remote.provider)
        if api_lookup:
            try:
                return api_lookup(remote, branch)
            except (Skip, FetchError) as exc:
                errors.append(str(exc))
        raise FetchError("; ".join(errors) if errors else f"{label}: lookup failed")
    # Unrecognised host (or no git metadata): keep the GitHub/GitLab CLI
    # probing that used to be the only current-branch path.
    errors = []
    try:
        return _gh_cli_branch_target(cwd)
    except (Skip, FetchError) as exc:
        errors.append(str(exc))
    try:
        return _glab_cli_branch_target(cwd)
    except (Skip, FetchError) as exc:
        errors.append(str(exc))
    raise FetchError(
        "No open pull/merge request for the current branch. "
        "Pass a PR/MR URL. "
        + (f"({'; '.join(errors)})" if errors else "")
    )


def resolve_number(number: str, cwd: str) -> Target:
    remotes = git_remotes(cwd)
    if not remotes:
        raise FetchError(
            f"Number {number} needs a git remote pointing at a supported provider "
            "(GitHub, GitLab, Bitbucket, Gitea/Forgejo, Azure DevOps), "
            "or a full PR/MR URL."
        )
    for _, url in remotes:
        target = target_from_remote(number, url)
        if target and target.provider != "unknown":
            return target
    if remotes:
        fallback = target_from_remote(number, remotes[0][1])
        if fallback:
            return fallback
    raise FetchError(
        f"Could not resolve pull/merge request {number} from git remotes: no remote "
        "points at a supported provider (GitHub, GitLab, Bitbucket, Gitea/Forgejo, "
        "Azure DevOps). Pass a full PR/MR URL."
    )


def fetch_brief(target: Target, cwd: str | None) -> Brief:
    fetchers = FETCHERS.get(target.provider, FETCHERS["unknown"])
    errors: list[str] = []
    for fetcher in fetchers:
        try:
            return fetcher(target, cwd)
        except Skip as exc:
            errors.append(f"{fetcher.__name__}: {exc}")
        except FetchError as exc:
            errors.append(f"{fetcher.__name__}: {exc}")
            # 404-style failures on a known host should not keep fishing forever,
            # but git refs can still exist when the API is private.
            if fetcher is not fetch_git and fetch_git in fetchers:
                continue
            break
    label = PROVIDER_LABELS.get(target.provider, target.provider)
    if target.provider == "unknown":
        raise FetchError(
            "Failed to fetch pull/merge request "
            f"{target.url or target.number}: " + "; ".join(errors)
        )
    raise FetchError(
        f"{label}: failed to fetch pull/merge request "
        f"{target.url or target.number}: " + "; ".join(errors)
    )


def resolve_target(arg: str | None, cwd: str) -> Target:
    if not arg:
        return resolve_current_branch(cwd)
    parsed = parse_argument(arg)
    if parsed.provider == "unknown" and parsed.number and not parsed.host:
        return resolve_number(parsed.number, cwd)
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a resume brief from a pull request or merge request."
    )
    parser.add_argument(
        "--cwd",
        default=str(os.getcwd()),
        help="Workspace cwd used to resolve a number or the current-branch PR",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="PR/MR URL, owner/repo#n, or number; omit for the current-branch PR",
    )
    args = parser.parse_args(argv)

    try:
        target = resolve_target(args.target, args.cwd)
        brief = fetch_brief(target, args.cwd)
    except FetchError as exc:
        raise SystemExit(str(exc)) from exc
    sys.stdout.write(render(brief))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
