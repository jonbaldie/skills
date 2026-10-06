## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default triage-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Uses a single-context layout. See `docs/agents/domain.md`.

### Releases

Before bumping the repository version or preparing a release, follow
[`docs/releases.md`](docs/releases.md) for Cursor plugin version updates and
release verification.

## Cursor Cloud specific instructions

There is no application server. The product is `install.sh` and the skills under `skills/`.

- Install `shellcheck`, `rsync`, and `pytest` before linting or testing: `sudo apt-get update`, then `sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends shellcheck rsync`, then `sudo python3 -m pip install --disable-pip-version-check pytest`. `pytest` is on `/usr/local/bin`.
- Syntax and lint match [`.github/workflows/installer-tests.yml`](.github/workflows/installer-tests.yml): `bash -n` on `install.sh`, `tests/*.sh`, and `skills/sync-jonbaldie-skills/scripts/**/*.sh`, then `shellcheck -e SC2016` on that set excluding `tests/install-ship-spec.sh`.
- Run the suite with `tests/run-all.sh`. On Linux, `tests/install-ship-spec.sh` skips because it also requires macOS `sandbox-exec`.
- Project install check: from an empty directory, run `bash /path/to/this/checkout/install.sh --project --agent cursor --yes --without-prereqs`. Shipped skills land in `.agents/skills/<name>/SKILL.md`. `skills/in-progress` and `skills/deprecated` stay out.
