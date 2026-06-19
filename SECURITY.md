# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for a
suspected vulnerability.

Use GitHub's private reporting: go to the repository's **Security** tab →
**Report a vulnerability** (this opens a private advisory only the maintainer can see).
If that option isn't available, open a regular issue that only says "security – please
enable private reporting" *without* any details, and the maintainer will follow up.

This is a small, single-maintainer project, so responses are best-effort. Please allow
a reasonable amount of time for a fix before any public disclosure.

## Supported versions

Only the latest version on the `main` branch (and the most recent tagged release) is
supported. There are no long-term support branches.

## Security posture

This tool is designed to be **local and minimal**, which keeps its attack surface small:

- **No third-party dependencies.** It uses only the Python standard library and a
  single-file Swift app, so there is no dependency supply chain to compromise.
- **Your Claude login token is never stored or transmitted by this tool.** `quota.py`
  reads it at runtime from the macOS Keychain (or `~/.claude/.credentials.json`), uses it
  for a single request to the official `api.anthropic.com`, and never writes it to disk
  or prints it. Usage data under `~/.claude/projects` is read-only and never modified.
- **Network surface:**
  - `quota.py` → `api.anthropic.com` only (to read your real rate-limit %).
  - The dashboard's local server binds to `127.0.0.1` only (not reachable from the network).
  - An **optional, off-by-default** update check fetches a version number from GitHub;
    it sends no data about you and stays silent unless you enable it.

## Scope

In scope: anything that could leak your token/credentials, write or modify data outside
the tool's own caches, expose the local dashboard beyond `127.0.0.1`, or run unexpected
code. Out of scope: the accuracy of usage estimates, and the ~1% rounding difference
between Anthropic's rate-limit headers and the web usage page.
