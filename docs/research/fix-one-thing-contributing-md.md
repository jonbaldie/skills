# Research: should `fix-one-thing` read `CONTRIBUTING.md`?

Researched 2026-09-25 against GitHub Docs, the CONTRIBUTING files of eleven
public repositories fetched from `raw.githubusercontent.com`, and the
AGENTS.md, EditorConfig and Claude Code docs.

## What GitHub says CONTRIBUTING.md is for

GitHub describes contributor guidelines as a way to "communicate expectations"
so that contributions are "well-formed", with fewer badly made pull requests and
issues. It suggests they cover steps for creating good issues or pull requests,
links to external docs, mailing lists or a code of conduct, and community and
behavioural expectations. It does not mention code style.
[Setting guidelines for repository contributors](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors).

GitHub looks for the file in `.github/` first, then the repository root, then
`docs/`. It links the file when someone opens an issue or pull request.
[Same page](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors);
[community health file precedence](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file).
In the community health file list, CONTRIBUTING "communicates how people should
contribute to your project".
[Supported file types](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file#supported-file-types).

## CODING_STANDARDS.md is a local convention

GitHub's community health files are CODE_OF_CONDUCT, CONTRIBUTING, discussion
forms, FUNDING, issue and PR templates, SECURITY and SUPPORT. None of them is a
coding-standards file.
[Supported file types](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file#supported-file-types).
I found no first-party spec for `CODING_STANDARDS.md`. Some projects use it,
but not in a fixed place: php-src keeps it at the root
([CODING_STANDARDS.md](https://github.com/php/php-src/blob/master/CODING_STANDARDS.md)),
while NASA's IKOS keeps it under `doc/`
([doc/CODING_STANDARDS.md](https://github.com/NASA-SW-VnV/ikos/blob/master/doc/CODING_STANDARDS.md)).
php-src's CONTRIBUTING checklist says to "Read [Coding standards](/CODING_STANDARDS.md)
before you start working", so there the two files have separate jobs.
[php-src CONTRIBUTING.md](https://github.com/php/php-src/blob/master/CONTRIBUTING.md).

## What real CONTRIBUTING files contain

I read eleven files. **Code** means rules a line of code can break. **Process**
means rules about issues, PRs, commits, legal terms, or links to other docs.

| Repo | Code rules | Process content |
| --- | --- | --- |
| [facebook/react](https://github.com/facebook/react/blob/main/CONTRIBUTING.md) | none | Only a link to an external guide |
| [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes/blob/master/CONTRIBUTING.md) | none | Link to guide, CLA |
| [golang/go](https://github.com/golang/go/blob/master/CONTRIBUTING.md) | none | Issue filing, link to contribution guide |
| [django/django](https://github.com/django/django/blob/main/CONTRIBUTING.rst) | none | "non-trivial pull requests ... without Trac tickets will be closed", code of conduct |
| [rails/rails](https://github.com/rails/rails/blob/main/CONTRIBUTING.md) | none; coding conventions are in an external guide | Bug reports, PR description. Cosmetic patches "will generally not be accepted" |
| [rust-lang/rust](https://github.com/rust-lang/rust/blob/main/CONTRIBUTING.md) | none | Links to dev guides, subtree PRs, LLM policy |
| [microsoft/vscode](https://github.com/microsoft/vscode/blob/main/CONTRIBUTING.md) | none | Issues, triage bots, PR link to wiki |
| [nodejs/node](https://github.com/nodejs/node/blob/main/CONTRIBUTING.md) | none | PR limits, unauthorised bots "subject to immediate moderation", AI policy, DCO |
| [angular/angular](https://github.com/angular/angular/blob/main/CONTRIBUTING.md) | "Coding Rules": tests required, public APIs documented, Google TS style, 100-column wrap | CLA, branch workflow, `<type>(<scope>): <short summary>` commits |
| [atom/atom](https://github.com/atom/atom/blob/master/CONTRIBUTING.md) (archived) | JS, CoffeeScript, specs and docs style guides | PR template, commit message rules |
| [php/php-src](https://github.com/php/php-src/blob/master/CONTRIBUTING.md) | "Use only `/* */` style comments"; links to CODING_STANDARDS.md | Patch submission, testing checklist |

Only three of eleven have code-level rules. All eleven have process rules. Big
projects often reduce CONTRIBUTING to a link to a longer guide somewhere else
(React, Kubernetes, Go, Rust, VS Code, and Node's `doc/contributing/`).

## What this means for the skill

- **As a source of violations it adds little.** Most files have no code rules.
  Where they do, the rules are often enforced by tools already: Angular says
  "An automated formatter is available", and Atom says its JavaScript is linted
  with Prettier. Mining it for violations would also weaken the skill's "stop if
  there is no `CODING_STANDARDS.md`" gate.
- **It does govern the skill's PR step.** Angular requires a commit format and a
  CLA. Atom requires its PR template. Django closes non-trivial PRs that have no
  ticket. Rails generally rejects cosmetic patches, which is exactly the kind of
  PR this skill produces. Node moderates unauthorised bots, and Node and Rust
  both have AI or LLM policies. An agent that ignores these can open a PR the
  maintainers reject on sight.
- **PR templates are a related case.** GitHub stores them at
  `pull_request_template.md` in the root, `docs/` or `.github/`, and fills the PR
  body from them.
  [Creating a pull request template](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository).

## Other places standards live

- **AGENTS.md**: a "README for agents"; its suggested sections include code
  style guidelines and commit or PR guidelines. [agents.md](https://agents.md/)
- **CLAUDE.md**: Claude Code recommends it for "coding standards, architectural
  decisions, naming conventions". [Claude Code memory docs](https://code.claude.com/docs/en/memory)
- **.editorconfig**: formatting rules that editors apply.
  [editorconfig.org](https://editorconfig.org/)
- **Linter and formatter configs**: usually enforced by tools already (see
  Angular and Atom above), so there is little for a manual fix to add.

## Recommendation

**Read CONTRIBUTING.md for a narrower purpose.** Keep `CODING_STANDARDS.md` as
the only source of violations. Read `CONTRIBUTING.md` only to follow its PR
process, and stop if it rules out this kind of PR.

Suggested wording, placed after the first line of the skill:

```
If `CONTRIBUTING.md` exists (in `.github/`, the root, or `docs/`), follow its
branch, commit and PR rules, and the repo's PR template if it has one. Take no
violations from it. If it rejects PRs like this one, stop and say so.
```

Separately, the skill does not say where `CODING_STANDARDS.md` lives. IKOS keeps
it under `doc/`, so a skill that only checks the root would wrongly stop.
