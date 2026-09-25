# Research: GitHub plugins for Cursor Cloud Agents

Researched 2026-09-23 against Cursor documentation and a Cursor staff response.

## Recommended route: a team marketplace

GitHub-hosted marketplace plugins can be provisioned for Cloud Agents. Cursor
staff confirmed on 2026-09-19 that the cloud provisioner supports GitHub source
repositories and Cursor-hosted mirrors; other providers can import successfully
for the IDE yet fail to provision in cloud runs.
[Cursor staff confirmation](https://forum.cursor.com/t/cloud-agents-marketplace-plugins-hosted-on-azure-devops-dev-azure-com-are-silently-dropped-github-hosted-plugins-install-fine/172143/5).

For this repository:

1. Open Cursor **Dashboard → Plugins & MCPs**.
2. Under **Team Marketplaces**, choose **Add Marketplace → Import from Repo**.
3. Enter `https://github.com/jonbaldie/skills` and connect GitHub if prompted.
4. Review and add `jonbaldie-skills` using **Add to Marketplace**.
5. Set marketplace access and the plugin's installation mode. **Default On**
   installs by default; **Required** prevents users uninstalling it.
6. Optionally enable **Auto Refresh**, then save. It needs the Cursor GitHub App
   installed on the repository and reindexes tracked-branch pushes at most once
   every ten minutes. **Refresh** provides a manual update.

Team marketplaces require Teams or Enterprise: Teams allows one; Enterprise
allows unlimited marketplaces and requires an admin to add them.
[Cursor plugin documentation](https://cursor.com/docs/plugins#add-a-team-marketplace).

The repository is already packaged for this flow:
[marketplace.json](../../.cursor-plugin/marketplace.json) names
`jonbaldie-skills` with source `./`, and
[plugin.json](../../.cursor-plugin/plugin.json) supplies its version and
`./skills/` component directory. No new manifest is needed.

After enabling it, start a fresh Cloud Agent and ask it to list or invoke one
of the plugin's skills. This is a practical verification step: the public docs
do not specify whether already-running agents refresh plugin installations.

## Personal installation and cloud skill sync

Cursor documents importing a repository through **Customize → From GitHub
Repository**, provided it contains `.cursor-plugin/marketplace.json`, then
installing its plugin. That documents the import flow; it does not explicitly
establish that a personal desktop plugin installation propagates to cloud runs.
[Repository import documentation](https://cursor.com/docs/skills#installing-skills-from-a-repository).

For personal Cloud Agents, the explicit documented route is personal skill
sync. Copy each skill from this repository's `skills/<name>/` into Cursor's
personal directory, `~/.cursor/skills/<name>/`. The repository's
[installer](../../install.sh) cannot do this: `--global --agent cursor` installs
into `~/.agents/skills/`. Follow the README's
[Cursor skill sync](../../README.md#cursor-skill-sync) rule. Then open **Settings → Agents → Context and Tools → Sync Skills for
Cloud Agents**, enable it and confirm. Sync is private and covers only
`~/.cursor/skills/`; it excludes `~/.agents/skills/` and other local files.
Team administrators can disable it under **Security & Identity**.
[Cloud skill sync documentation](https://cursor.com/docs/skills#use-personal-skills-with-cloud-agents).

This fallback delivers the repository's skills; it is not a documented way
to sync an entire plugin's hooks, rules, or MCP configuration.
