# claude-usage-peek

**English** · [中文](README.zh.md) · [日本語](README.ja.md)

> Built entirely with [Claude Code](https://claude.com/claude-code).

A macOS menu-bar app for keeping an eye on your Claude usage.

- **Collects nothing about you** — no tracking, no analytics; nothing about you ever leaves your Mac.
- **Lightweight** — just a small menu-bar icon; nothing to `pip install`, no background heavy lifting.
- **Safe** — read-only. It never changes your Claude data.

A 🤖 icon sits in your menu bar showing how much of your 5-hour quota is left.
Click it for a small panel with your 5h / 7d limits and reset times, or expand it
into a full HTML dashboard with charts and a usage heatmap.

> **🔒 Local & safe.** Everything runs on your machine. **Your usage data is never
> uploaded, sent out, or routed through any third party.** Nothing in your Claude data
> is modified. The only network access is a single read to the **official
> `api.anthropic.com`**, using your own Claude Code login token, to fetch your real
> quota % (read-only; no data sent; the token is never written to disk or printed).

## Requirements

- **macOS 13+**
- **Python 3** — the engine that reads your usage and your quota (`python3` on your PATH)
- **Xcode Command Line Tools** (for `swiftc`, to build the app once) —
  install with `xcode-select --install`

> No `pip install`, no third-party packages, no account, no configuration.

## Install

1. **Download this folder** (clone or download the ZIP).
2. **Build the app** — double-click `build_menubar.command` in Finder, or in Terminal:
   ```bash
   bash build_menubar.command
   ```
   It asks for your **interface language** (English / 中文 / 日本語 — default English;
   you can change it later), compiles, and puts **Claude Usage Bar.app** on your Desktop.
3. **Open the app** — double-click `Claude Usage Bar.app`. A 🤖 appears in your menu bar.

> Moved the folder? Just run `build_menubar.command` again.
>
> To start it automatically at login: **System Settings → General → Login Items**, add the app.

## Using the app

- **Left-click** the 🤖 → a panel showing:
  - **5-hour window** and **7-day window** progress bars (fill = how much you've used,
    green → orange → red), the **remaining %**, and the **reset time**
  - **🔄 Refresh** — re-fetch your official quota
  - **📊 Open dashboard →** — launch the full HTML dashboard in your browser
- **Right-click** the 🤖 → a small menu: **Refresh quota** / **Open dashboard** /
  **Language** / **Quit**.

### Changing the language

You pick a language when you install (default English). To change it later, **right-click
the 🤖 icon → Language**, then choose **English / 中文 / 日本語**. It switches right away and
is remembered the next time you open the app — no rebuild needed.

## What the numbers mean

- **5h / 7d %** = your **whole Anthropic account's** official limits (web, desktop,
  Claude Code, API — this is Anthropic's unified limit), fetched from the official API.
- **The dashboard charts** = your **local *Claude Code* usage** (terminal CLI, VS Code
  and other IDE extensions — anything that writes sessions to `~/.claude/projects/`).
  It does **not** include claude.ai web or the Claude desktop chat app.

The dashboard is a self-contained HTML page (no JavaScript, no CDN) with cards for
today / this week / this month / all-time tokens, the official 5h/7d bars with reset
countdowns, a GitHub-style daily heatmap, an hourly bar chart, and a per-model breakdown.
Its local server listens on `127.0.0.1` only.

## Uninstall

```bash
bash uninstall.command   # or double-click it in Finder
```

It quits the menu-bar app and background services, removes the Desktop app, caches,
logs, and language preference, and (optionally) deletes the folder. Nothing system-level
was ever installed, so removal is clean.

## Advanced — command-line tools (optional)

The app is powered by small, auditable Python scripts you can also run directly:

```bash
python3 usage.py            # per-day + per-model token summary (add --json for raw)
python3 dashboard.py        # generate & open the HTML dashboard
python3 dashboard.py --serve  # live dashboard at http://127.0.0.1:8787
python3 quota.py            # print official 5h/7d % (one call to api.anthropic.com)
python3 watch.py            # background watchdog: macOS notification at 50/75/90%
```

You can also wire `usage.py` into the Claude Code terminal **statusline** — see
[usage.py](usage.py). (The statusline renders in the terminal CLI only, not the VS Code panel.)

## Security

- The usage stats read local files only and **never go online**. The only network
  call is `quota.py`: one request to **api.anthropic.com** (official) with your local
  Claude Code token to read your real quota %. **No third party; the token is never
  written to disk or printed.** Data under `~/.claude/projects` is never modified.
- The menu-bar app reads only the quota cache (`~/.claude/usage-peek-quota.json`) and
  launches the bundled Python scripts; it makes no network calls of its own.
- No third-party dependencies, single-file scripts you can audit: [usage.py](usage.py),
  [quota.py](quota.py).
