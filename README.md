# Omalaunch: GitHub

An external [Omalaunch](https://github.com/daniel-lemky/omalaunch) menu extension for GitHub.

It keeps repositories, issues, pull requests, and notifications out of global search by default. They remain available in the GitHub menu and can be enabled through configuration. Repository, issue, pull request, and notification lists include their latest update date. On-demand submenus and structured documents keep the root response small. Repository menus show open issue, open pull request, and unread notification counts. Their Actions submenu shows recent workflow runs with semantic status badges and job details. Repository documents show project data. Issue, pull request, and notification documents show metadata, safe host-rendered Markdown body text, copyable code blocks, and Open and Copy URL actions. Pull request details also show individual check runs and their combined result.

The provider is read-only except for the explicit **Mark as read** notification action and its local shortcut-star state. Press Ctrl+S on general or repository menu items to add or remove top-level Omalaunch shortcuts. Repository shortcuts include the repository name, such as `acme/widgets · Actions`.

## Requirements

- Omalaunch with dynamic `submenu` and `document` row support
- Python 3
- [GitHub CLI](https://cli.github.com/) authenticated for `github.com`: `gh auth login`
- `xdg-open`
- `wl-copy`
- `omarchy-launch-editor`
- `omarchy-agent`

GitHub Enterprise Server is not supported in version 1.

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

JSONC comments and trailing commas are accepted. See [`config.example.jsonc`](config.example.jsonc) for the complete version-1 structure. By default, GitHub data is excluded from global search. Repositories, issues, pull requests, and notifications remain available in their GitHub menus. Users can enable repository search with an `owned` or `visible` scope, or enable exact items through overrides.

Each repository can be enabled or disabled through `repositories.globalSearch.overrides`. Issues and pull requests use exact `owner/repository#number` overrides. `globalSearch.excludedRepositories` removes a repository and its work items unless an exact item override enables one. Configuration affects global search only; it does not remove rows from GitHub menus. Invalid, oversized, over-depth, or unknown configuration is ignored and the safe defaults remain active. The Configuration menu shows a bounded error row that opens an invalid file for repair.

## Provider interface

`bin/omalaunch-github root` returns the four static GitHub categories without a network request. Omalaunch runs `bin/omalaunch-github global-search` independently to load recent GitHub records for global search. Other provider commands are internal targets for host-rendered submenus, documents, and the mark-read action.

All `gh` calls use direct subprocess argument arrays, a request timeout, and no shell. Errors go to stderr and return a nonzero status. Each menu response has at most 100 rows.

The provider keeps list results for 60 seconds and detail documents for 30 seconds under the Omalaunch extension state directory. If a normal navigation request fails, the provider uses an expired but valid cache entry when one exists; explicit Ctrl+R refresh failures remain visible. Global-search preload requests only the entity groups enabled by configuration. With the default configuration, it makes no GitHub request. Opening a repository warms its issue, pull request, and notification lists while it loads their counts. Ctrl+R uses the declared live refresh command and bypasses the cache. Actions lists are limited to 30 recent runs.

## Test

```sh
python -m unittest discover -s tests -v
```

Tests use a fake `gh` executable and do not access GitHub.
