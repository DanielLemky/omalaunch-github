# Omalaunch: GitHub

An external [Omalaunch](https://github.com/daniel-lemky/omalaunch) menu extension for GitHub.

It shows recent repositories, open issues and pull requests related to you, and unread notifications in global search. Repository, issue, pull request, and notification lists include their latest update date. On-demand submenus and structured documents keep the root response small. Repository menus show open issue, open pull request, and unread notification counts. Their Actions submenu shows recent workflow runs with semantic status badges and job details. Repository documents show project data. Issue, pull request, and notification documents show metadata, safe host-rendered Markdown body text, copyable code blocks, and Open and Copy URL actions. Pull request details also show individual check runs and their combined result.

The provider is read-only except for the explicit **Mark as read** notification action.

## Requirements

- Omalaunch with dynamic `submenu` and `document` row support
- Python 3
- [GitHub CLI](https://cli.github.com/) authenticated for `github.com`: `gh auth login`
- `xdg-open`
- `wl-copy`

GitHub Enterprise Server is not supported in version 1.

## Install

Install and enable the plugin:

```sh
omarchy plugin add https://github.com/DanielLemky/omalaunch-github --enable
```

Omalaunch reads `manifest.json` and loads `omalaunch.json`. Refresh Omalaunch after installation.

## Provider interface

`bin/omalaunch-github root` returns the four static GitHub categories without a network request. Omalaunch runs `bin/omalaunch-github global-search` independently to load recent GitHub records for global search. Other provider commands are internal targets for host-rendered submenus, documents, and the mark-read action.

All `gh` calls use direct subprocess argument arrays, a request timeout, and no shell. Errors go to stderr and return a nonzero status. Each menu response has at most 100 rows.

## Test

```sh
python -m unittest discover -s tests -v
```

Tests use a fake `gh` executable and do not access GitHub.
