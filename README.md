# Omalaunch: GitHub

An external [Omalaunch](https://github.com/daniel-lemky/omalaunch) menu extension for GitHub.

Global search always includes static shortcuts for **GitHub · Repositories**, **GitHub · Issues**, **GitHub · Pull Requests**, and **GitHub · Notifications**. The shortcuts need no GitHub request and accept aliases such as `repos` and `prs`. They stay out of the top-level view unless the user manually stars them. Individual repository, issue, pull request, and notification results remain disabled by default and can be enabled through configuration. Their lists include the latest update date. On-demand submenus and structured documents keep the root response small. Repository menus show open issue, open pull request, and unread notification counts. Their Actions submenu shows recent workflow runs with semantic status badges and job details. Repository documents show project data. Issue, pull request, and notification documents show metadata, safe host-rendered Markdown body text, copyable code blocks, and Open and Copy URL actions. Pull request details also show individual check runs and their combined result.

The provider is read-only except for the explicit **Mark as read** notification action and its local shortcut-star state. Press Ctrl+S on repositories, general menu items, or repository menu items to add or remove permanent top-level Omalaunch shortcuts. Repository shortcuts include the repository name, such as `acme/widgets · Actions`. Optional recent Actions runs are temporary top-level rows. They do not change or use these manual stars.

## Requirements

- Omalaunch with dynamic `submenu` and `document` row support
- Python 3
- [GitHub CLI](https://cli.github.com/) (`gh`)
- `xdg-open`
- `xdg-terminal-exec`
- `wl-copy`
- `omarchy-launch-editor`
- `omarchy-agent`

GitHub Enterprise Server is not supported in version 1.

If `gh` is missing, Omalaunch keeps the extension visible and offers to install the Arch package `github-cli`. Omalaunch owns this fixed executable-to-package mapping. The plugin manifest cannot select an installation command. Omalaunch shows the exact `omarchy pkg add github-cli` command and requires confirmation before it opens a visible, held terminal. Reopen Omalaunch after the command finishes to recheck the dependency.

A nonempty `GH_TOKEN` or `GITHUB_TOKEN`, or a successful bounded local `gh auth token` lookup, makes GitHub ready to use. The lookup sends stdout and stderr to `/dev/null`. The plugin does not store or print the token. Root and static global-search menus open immediately. They do not make a GitHub network request and do not claim that GitHub verified the credential.

A known GitHub HTTP or API authentication rejection marks the current credential source as invalid. The plugin then removes cached GitHub data and shows only **Set up GitHub** on the root, global-search preload, manual-star, and automatic Actions surfaces. Star state stays on disk but is hidden. This invalid state remains after a new provider process starts. **Recheck** can verify the active account and restore all menus. A change between an environment credential and a stored credential also restores the local ready state. A successful verification is cached for five minutes. After it expires, the credential stays locally configured and ready to use.

This design has one tradeoff: a revoked token can expose static menus until the first GitHub API request rejects it. Network, proxy, rate-limit, permission, and other uncertain failures do not mark authentication as invalid and do not gate static menus. A failed transient Recheck also returns to the local ready state.

**Sign in to github.com** opens `env -u GH_TOKEN -u GITHUB_TOKEN gh auth login --hostname github.com` in a visible interactive terminal. This change applies only to that child command and preserves all other environment values. It cannot repair an invalid token in the launcher's parent environment. Correct or remove an invalid `GH_TOKEN` or `GITHUB_TOKEN` where the launcher environment is set, and then reopen the launcher. **Recheck** actively verifies only the active `github.com` account. A stale inactive account does not invalidate the active account. The plugin does not request classic scopes, print or store tokens, or automatically expand permissions after GitHub denies a request. Fine-grained tokens can work when their permissions cover the requested resources. Known GitHub authentication, permission, rate-limit, and network failures use separate bounded guidance. Other local or proxy failures use a neutral message.

## Install

Install and enable the plugin:

```sh
omarchy plugin add https://github.com/DanielLemky/omalaunch-github --enable
```

Omalaunch reads `manifest.json` and loads `omalaunch.json`. Refresh Omalaunch after installation.

## Configuration

The optional configuration file is:

```text
~/.config/omarchy/omalaunch/extensions/quantumfire.github.jsonc
```

The GitHub root menu includes **Configuration**. If the file is missing, either action first creates it from the bundled example with private permissions. **Open config file** opens it with the default Omarchy editor. **Edit with agent** starts the default Omarchy coding agent with the path and schema example in its prompt. Both actions close Omalaunch as soon as the editor or agent starts.

JSONC comments and trailing commas are accepted. See [`config.example.jsonc`](config.example.jsonc) for the complete version-1 structure. By default, individual GitHub data is excluded from global search. The four static root shortcuts remain searchable, and Configuration remains excluded. Repositories, issues, pull requests, and notifications remain available in their GitHub menus. Users can enable repository search with an `owned` or `visible` scope, or enable exact items through overrides.

Each repository can be enabled or disabled through `repositories.globalSearch.overrides`. Issues and pull requests use exact `owner/repository#number` overrides. `globalSearch.excludedRepositories` removes a repository and its work items unless an exact item override enables one.

`actions.topLevel` is disabled by default. When enabled, it checks only its explicit `repositories` list. It never scans the account. `statuses` accepts `queued`, `in_progress`, `success`, and `failure`. Active selected runs stay visible while active. Completed runs stay visible for `completedWithinMinutes`, up to the global `limit`. The provider uses `completed_at` when GitHub supplies it and otherwise uses `updated_at` as the completion-time fallback. Active runs sort first. Recent failures sort before other completions. Repository and run ID break ties. Global search can stay disabled for all entities; this does not prevent temporary rows.

Invalid, oversized, over-depth, or unknown configuration is ignored and the safe defaults remain active. The Configuration menu shows a bounded error row that opens an invalid file for repair.

## Provider interface

When a local credential is configured, `bin/omalaunch-github root` returns four concise GitHub categories and Configuration without a network request. When no credential exists, or after a known authentication rejection, it returns only Set up GitHub. Global search uses the stable `general:*` identities and adds the `GitHub ·` label prefix. Omalaunch runs `bin/omalaunch-github global-search` independently to load enabled recent GitHub records and the four static shortcuts. Other provider commands are internal targets for host-rendered submenus, documents, and the mark-read action.

All `gh` calls use direct subprocess argument arrays, a request timeout, and no shell. Errors go to stderr and return a nonzero status. Each menu response has at most 100 rows.

The provider keeps list results for 60 seconds and detail documents for 30 seconds under the Omalaunch extension state directory. If a normal navigation request fails, the provider uses an expired but valid cache entry when one exists. It does not use stale data after a known authentication rejection. Explicit Ctrl+R refresh failures remain visible. Omalaunch polls enabled temporary top-level data every 60 seconds without overlapping requests. Actions preload accepts cached API data for at most 120 seconds after a network or other uncertain failure. The host then expires the old temporary snapshot, so old completed or active rows do not remain indefinitely. Preload requests only enabled global-search groups and explicit top-level repositories. With the default configuration, it returns only the four static global shortcuts and makes no GitHub request. Opening a repository warms its issue, pull request, and notification lists while it loads their counts. Ctrl+R on Actions lists and run details uses the declared live refresh command and bypasses the cache. Actions lists are limited to 30 recent runs.

## Test

```sh
python -m unittest discover -s tests -v
```

Tests use a fake `gh` executable and do not access GitHub.
