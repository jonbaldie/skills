## Agent skills

### Version bumps and releases

When bumping the repository version or preparing a release, update the Cursor
plugin versions in the same change. Use `.cursor-plugin/marketplace.json` to
identify every plugin manifest; the current manifest is
`.cursor-plugin/plugin.json`. Set each manifest's `version` to the repository's
target release version, without the tag's leading `v`.

Before tagging or publishing, verify that every plugin manifest in the commit
being released contains valid JSON and matches the release version. A version
bump or release is complete only when all Cursor plugin versions match.

### Issue tracker

Issues are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default triage-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Uses a single-context layout. See `docs/agents/domain.md`.
