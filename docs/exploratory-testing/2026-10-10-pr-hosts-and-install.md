# Exploratory pass: PR hosts, install, and sync

2026-10-10. Checkout `c8af523` (`origin/main`). macOS 26.6.2, Bash
3.2.57, Python 3.14.5, `gh` logged in as `jonbaldie`. Isolated project
directories and isolated `HOME` values under the fleet scratch directory.
Live `~/.agents`, `~/.cursor`, and agent session stores were not written.

Confirmed bugs: [#188](https://github.com/jonbaldie/skills/issues/188),
[#189](https://github.com/jonbaldie/skills/issues/189),
[#190](https://github.com/jonbaldie/skills/issues/190),
[#191](https://github.com/jonbaldie/skills/issues/191).

This pass covers hosts and install variations the
[2026-09-26](2026-09-26-skills.md) and
[2026-10-03](2026-10-03-resume-skills.md) passes left unexplored.
`glab` is not installed, so GitLab current-branch lookup used the API.

## Journeys

1. Resume interrupted work from a non-GitHub pull or merge request
   (`resume-from-pr`).
2. Install the collection so an agent can use it (`install.sh`).
3. Update an installed project (`sync-skills.sh`, then
   `copy-to-skill-dirs.sh`).

## Journey 1: resume from a non-GitHub PR

Goal: the extractor prints a brief the continuation can act on. The
skill's done condition is knowing `provider`, `url`, `number`, `head`,
and `head_sha`. Those values should match the host. Documented call:

```bash
python3 skills/resume-from-pr/scripts/extract-pr.py [url-or-number]
```

No argument looks up the open PR for the current branch. A bare number
uses the current repository's remote.

| Action | Result |
| --- | --- |
| GitLab URL `gitlab-org/cli!4037` | Exit 0. Title, head, and full `head_sha` match the API. Two files match `/diffs`. Pipeline `success` matches. |
| GitLab URL `!4044`, bare `4044`, and no argument on that source branch | Exit 0. Same MR each time. |
| GitLab branch with no open MR | Exit 1. `no open pull request for branch 'no-such-branch-et'`. |
| Codeberg URL `forgejo/forgejo` pulls/14781 | Exit 0. Title, base, and full SHA match the API. Discussion includes the coverage comment. |
| Codeberg no-argument lookup for `upgrade-zoekt` and `renovate/forgejo-github.com-urfave-cli-v3-3.x` | Exit 0. Pulls 14016 and 13949, both past the first page of 50. Head branches match. |
| Gitea URL, bare `1126`, and no argument on `stack/05-cli` | Exit 0. Title, head, and full SHA match the API. |
| Bitbucket URL 5455, bare `5455`, and no argument on that branch | Exit 0. Title, author, and both diffstat files match the API. |
| Bitbucket merged URL 5470 | Exit 0. Title and base match. |
| `https://example.com/not-a-pr` and a GitLab issue URL | Exit 1. `Could not parse as a pull/merge request URL`. |
| GitLab MR 99999999 | Exit 1. Names `glab` missing, the 404, and the git fallback. |
| No remotes, no argument | Exit 1. `No open pull/merge request for the current branch`. |
| Codeberg `/pull/14781` (not `/pulls/`) | Exit 1. Codeberg itself returns 404 for that path. The extractor treats `/pull/` as GitHub and says so. |

### Confirmed: Gitea and Codeberg briefs say GitHub

[#188](https://github.com/jonbaldie/skills/issues/188).

Every successful Gitea and Codeberg brief above starts `provider: github`
while `host` is `gitea.com` or `codeberg.org`. Replayed on both hosts, by
URL, by number, and by current branch. The skill lists Gitea/Forgejo as
its own provider. #153 already describes the stamp; this is the user-facing
failure.

### Confirmed: GitLab `repo` is the merge-request reference

[#189](https://github.com/jonbaldie/skills/issues/189).

```text
repo: gitlab-org/cli!4044
```

The project path is `gitlab-org/cli`. The same shape appears for `4037`
and for number and current-branch lookup. Other briefs put `owner/repo`
in that field (`atlassian/aui`, `gitea/tea`). Replayed on both MRs.

### Confirmed: Bitbucket `head_sha` cannot be fetched

[#190](https://github.com/jonbaldie/skills/issues/190).

The brief prints `head_sha: fe55684f21d5` for #5455 and
`head_sha: df810768a858` for #5470. `git fetch --depth 1 origin` of each
exits 128: `couldn't find remote ref`. The commit API linked from the
pull-request payload has the 40-character id
`fe55684f21d513aa09e86eaf639f3c6d3556d991`, and fetching that exits 0.
Current-branch lookup prints the same 12-character value.

### Confirmed: a dropped connection is a traceback

[#191](https://github.com/jonbaldie/skills/issues/191).

The second Codeberg URL call exited 1 with
`http.client.RemoteDisconnected` and a stack from `http_page`. A later
call of the same URL exited 0. Other fetch failures are one-line errors.

Reduced replay, disclosed: a TLS server on `gitea.localhost` that
completes the handshake and closes, with `SSL_CERT_FILE` trusting its
certificate. Both runs exited 1 with an uncaught
`ConnectionResetError: [Errno 54] Connection reset by peer`. No brief and
no `failed to fetch` line. The ordinary traceback is kept; the local
server only shows the same uncaught class.

## Journey 2: install

Goal: skills from this checkout are on disk for the named agent.
`in-progress/` and `deprecated/` stay out. Documented command, declining
prerequisites:

```text
cd <git project>
printf 'n\n' | ../jonbaldie-skills/install.sh --agent pi --yes
```

`JONBALDIE_SKILLS_REPO` pointed at this checkout so the run exercised
`c8af523`, not a second clone of GitHub. Exit 0. Twenty-four `SKILL.md`
files under `.agents/skills`. `.pi/skills/options` is a symlink to the
canonical copy. No `tutor` or `ship-spec`. Re-run exited 0 and left the
same set.

Variations, each from a clean directory except the re-run:

| Action | Result |
| --- | --- |
| `--agent not-an-agent` | Exit 1. `Unsupported agent: not-an-agent` and the supported list. No `SKILL.md` left behind. |
| `--skill does-not-exist` | Exit 1. `No matching skills found`. Nothing left behind. |
| `--skill options --skill mutation-testing` | Exit 0. Only those two. |
| Path with a space | Exit 0. `options` installed. |
| Directory that is not a git repo | Exit 0. OpenCode `options` installed. |
| `--copy --agent pi --agent claude-code --skill options` | Exit 0. Real directories under `.pi/skills` and `.claude/skills`. No `.agents/skills`. Matches `--copy`'s help, which says agent dirs rather than the symlink layout. |
| `--global --agent cursor --without-prereqs` in an isolated home | Exit 0. 24 skills under `~/.agents/skills`. `~/.cursor/skills` was not created. Re-run exited 0. Matches the README. |
| `--with-prereqs` against a local mattpocock tree that also contains `options` | Exit 1. Names both source directories. No `SKILL.md` left behind. |
| Script piped to `bash` with no controlling terminal | Exit 0. Printed the question, took the `[y/N]` default, installed this collection only under `~/.agents/skills`. |

## Journey 3: sync

Goal: `sync-skills.sh <project>` installs both collections into
`<project>/.agents/skills`, reports both commit ids, replaces managed
skills, and leaves unrelated skills alone.

`JONBALDIE_SKILLS_REPO` was this checkout. `MATTPOCOCK_SKILLS_REPO` was a
depth-1 clone of `mattpocock/skills` at `49dd158`. No skill name overlaps
that clone. Ordinary run exited 0.

```text
mattpocock/skills commit: 49dd158d1076134a641b33efb035946536778336
jonbaldie/skills commit: c8af52399b594478eceb4f4934c962fdfe3a5ac3
Canonical destination: <project>/.agents/skills
```

55 `SKILL.md` files. Unrelated `.agents/skills/unrelated/content.txt`
kept. `tutor` and `ship-spec` absent. `ask-matt` present. A stale
`options/stale.txt` was gone after a second run; the unrelated file
remained. A manifest entry `retired-skill` plus its directory was removed
(`removed retired skill retired-skill`).

`copy-to-skill-dirs.sh <project> .claude/skills` copied managed skills
and left `.claude/skills/unrelated` alone. An absolute destination
outside the project received the same 55 skills. `.` and `..` were
rejected and did not write a `SKILL.md` at the project root. A missing
project directory exited 1 with `project directory does not exist` for
both scripts.

A sync against the colliding local mattpocock tree exited 1 before
installing and left the unrelated file in place. That tree is not the
upstream collection; the real clone has no overlapping names.

No confirmed bug on journeys 2 or 3.

## Rejected

- Gitea current-branch lookup misses pulls past page 1 (#174). Pulls
  14016 and 13949 were found with no argument.
- No-terminal one-liner answers yes (#140). It printed the question and
  skipped mattpocock/skills.
- Public GitLab discussions are dropped with no note. The brief has a
  `## Gaps` section: discussions fetch failed after 0 items, HTTP 401.
  Unauthenticated `notes` and `discussions` both return 401, so the gap
  matches the host.
- Installer ships `tutor` or `ship-spec`. Neither was installed.
- `copy-to-skill-dirs.sh .` writes a skill at the project root. Exit 1,
  no file.

## Unresolved

None on the journeys that ran.

## Not explored

Azure DevOps success path. Public projects checked (`azure-sdk/public`,
`python/cpython`) have no pull requests. A missing pull
`python/cpython` pullrequest/1 exited 1 and named the Azure 404. Bitbucket
Server. `promote-fork-pr-upstream` (publishing needs a second GitHub
account). `resume-from-agent` adapters for hermes, dirac, goose, cursor,
and gemini. The prose-only skills.

## Usability

Observations:

- GitLab briefs say `state: opened`. Bitbucket and Gitea briefs say
  `open` or `merged`.
- Codeberg pull 14781's `head` is `refs/pull/14781/head`, which is what
  the Codeberg API returns, not a branch name.
- `--copy` does not also fill `.agents/skills` when the selected agents
  use `.pi/skills` and `.claude/skills`. The help text says that. A later
  sync is a separate tree.

## Limitations

The one-liner and sync clones used the documented repo URL overrides so
this checkout was the jonbaldie source. Sync's mattpocock source was a
depth-1 clone of the public repository, not a second live clone during
the sync itself. The connection-reset comparison used a local TLS server
and a private `SSL_CERT_FILE`; the Codeberg traceback was recorded before
that. No Docker resources were created. Live agent session stores were
not read.
