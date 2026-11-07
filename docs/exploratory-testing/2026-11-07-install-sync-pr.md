# Exploratory pass: install, sync, and GitHub PR briefs

2026-11-07. Tested `origin/main` at `1b1d392ae575a589ad546291d391c29a52f5e3e2` on Linux with Bash, Git, rsync, and Python 3.14.4. The worktree held isolated projects, `HOME`, temporary files, and a local clone of `mattpocock/skills` at `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d`. The live agent skill directories and session stores were not used. The product has no dependency lockfile. No dependencies were installed.

One bug was confirmed and filed as [#243](https://github.com/jonbaldie/skills/issues/243). The pass did not attempt to reproduce every prior issue. The [earlier install and sync pass](2026-10-17-install-sync-copy.md) includes [#204](https://github.com/jonbaldie/skills/issues/204), and the [PR host pass](2026-10-10-pr-hosts-and-install.md) includes [#188](https://github.com/jonbaldie/skills/issues/188) through [#191](https://github.com/jonbaldie/skills/issues/191). Those findings are not asserted to be regressions here.

## Install selected skills for Pi

The goal was to install two requested skills into a project and make them readable through Pi's directory. With `JONBALDIE_SKILLS_REPO` set to the tested checkout, `install.sh --project --agent pi --without-prereqs --skill options --skill resume-from-pr` exited 0. Both canonical `SKILL.md` files existed, Pi's entries were symlinks, and the bytes read through Pi's `options` link matched the canonical file. See [install output](evidence/2026-11-07/install.log).

A repeat install of `options` exited 0 and left the skill readable. A sentinel added inside that managed skill disappeared. This is an observation about replacement, not a finding that the installer promises to preserve edits inside managed skills. An invalid agent exited 1 before installing a skill. See [repeat](evidence/2026-11-07/install-repeat.log) and [invalid agent](evidence/2026-11-07/install-invalid.log).

## Sync and copy managed skills

The goal was to install both collections, update a managed skill, preserve unrelated project content, and copy managed skills for Claude Code. The documented sync command exited 0 and reported both source commits. On a repeat run, a stale file inside managed `options` disappeared, an unrelated skill's sentinel remained, and the manifest existed. The copy command exited 0 and Claude's `options/SKILL.md` matched the canonical bytes, but it also printed the error described below. See [first sync](evidence/2026-11-07/sync-first.log), [repeat](evidence/2026-11-07/sync-repeat.log), and [copy](evidence/2026-11-07/copy.log).

As a failure variation, the prerequisite repository override pointed to a missing local path. Sync exited 128 and the existing manifest's SHA-256 was unchanged. This deliberate missing source is an environment failure, not a product bug. See [failure output](evidence/2026-11-07/sync-failure.log).

### Confirmed: named-agent copy emits a Bash error

[#243](https://github.com/jonbaldie/skills/issues/243). A named-agent copy reports `local: project_root: readonly variable` even when it succeeds. Users and scripts inspecting stderr can mistake the diagnostic for a failed or incomplete copy.

To replay from the checkout, create an isolated project with `.agents/skills/options/SKILL.md` copied from `skills/options/SKILL.md`, and write `options` on its own line in `.agents/sync-jonbaldie-skills.manifest`. Run `skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh "$project" --agent claude-code`. The expected result is a successful copy without a shell error. In two clean projects the command printed the error, exited 0, and wrote bytes matching the canonical skill. Copying to `.custom/skills` instead produced no error. See [replay 1](evidence/2026-11-07/copy-replay-1.log) and [replay 2](evidence/2026-11-07/copy-replay-2.log). An independent review identified the diagnostic in the original output; the reduced replay followed that review.

## Extract a GitHub PR brief

The goal was to obtain the provider, URL, number, head branch, and full head SHA for a real pull request. The documented extractor returned a brief for [PR #242](https://github.com/jonbaldie/skills/pull/242) using both its URL and the bare number. Both outputs matched the independently queried GitHub API for those fields. An issue URL was rejected with exit 1 instead of being treated as a PR. The extractor used the unauthenticated API fallback under the isolated `HOME`. See [URL](evidence/2026-11-07/pr-url.log), [number](evidence/2026-11-07/pr-number.log), [API](evidence/2026-11-07/pr-api.json), and [invalid URL](evidence/2026-11-07/pr-invalid.log). The brief is output only; this journey did not check out or alter the PR branch.

## Verification and limits

`RUN_ALL_SKIP=pytest tests/run-all.sh` passed 16 shell suites. It skipped pytest because this host had no pytest, and skipped the ship-spec suite because `sandbox-exec` was unavailable. See [suite output](evidence/2026-11-07/shell-tests.log). ShellCheck was also unavailable locally. The repository CI installs pytest and runs the full supported checks.

The pass did not exercise a live Pi agent, Claude Code discovery, other PR hosts, private PRs, the one-line network installer, or the prose-only skills. The local source overrides make the tested commits reproducible but do not test upstream clone availability during install or sync. No candidate remained unresolved in the exercised paths after the copy diagnostic was replayed.

The shell commands ran in the foreground. No browser, server, container, Docker image, or volume was started for this pass. [Resource registration](evidence/2026-11-07/resources.txt) and [cleanup verification](evidence/2026-11-07/cleanup.txt) record the scope and teardown.
