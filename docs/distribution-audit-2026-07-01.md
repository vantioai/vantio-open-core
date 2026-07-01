# Public Distribution Audit — 2026-07-01

**Trigger:** Zachary reported that Tier 1 installs were failing for real users via GitHub,
npm, and PyPI. This audit reproduces each install path exactly as a real user would and
identifies root causes.

---

## npm (`@vantio/cli`) — BROKEN. Root cause found and code-fixed; publish still requires human action.

**The bug:** The root README's "Get started in 60 seconds" quickstart is:

```bash
npm install -g @vantio/cli
vantio login          # validates + saves your API key once
vantio run node agent.js
```

Reproduced exactly. `npm install -g @vantio/cli` succeeds. `vantio login` fails immediately:

```
vantio: unknown command 'login'
```

**Root cause:** version drift between source and registry.
- Local `packages/vantio-cli/package.json`: **0.3.0** — has `run`, `login`, `logout`, `whoami`, `discover`
- What `npm view @vantio/cli` actually returns: **0.1.0**, published a month ago — only has `run`

Confirmed the 0.3.0-introducing commits (including the exact commit that added `login`,
`00ca55e feat: vantio login + key-prefilled dashboard quickstart...`) are present in
`origin/main`'s history. So the code reached GitHub. `.github/workflows/npm-publish.yml`
triggers on every push to `main` — it should have re-published on each of these pushes.
It did not. The registry has been stuck at 0.1.0 through four version bumps
(0.1.1 → 0.1.2 → 0.2.0 → 0.3.0).

**Why this went unnoticed:** the workflow's publish steps were written as:

```bash
pnpm publish --access public --no-git-checks || echo "Already published."
```

This swallows *every* failure mode into the same message — an expired/invalid `NPM_TOKEN`,
a network error, or a genuine "already published" condition all produce the same green
checkmark. Most likely cause given the pattern (4 consecutive silent no-ops across different
commits, different feature sets): `NPM_TOKEN` is invalid, expired, or was revoked at some
point after the 0.1.0 publish succeeded.

**Fixed in this session (`npm-publish.yml`):**
1. Publish steps now distinguish "already published" (tolerated, matches on the actual npm
   error string) from every other failure (now fails the job loudly with `::error::`)
2. Added a verification step that compares local `package.json` version against the live
   npm registry version after publishing — would have caught this exact drift on day one
3. Added `workflow_dispatch` trigger so this can be manually re-run once the token is fixed,
   without needing a dummy commit

**Still requires human action** (no npm publish credentials available in this environment):
1. Check `NPM_TOKEN` at `github.com/vantioai/vantio-open-core/settings/secrets/actions` —
   likely expired or revoked. Generate a new automation token at npmjs.com and update the secret.
2. Re-run the workflow manually (Actions tab → "Publish to npm" → "Run workflow") once the
   token is confirmed valid.
3. Verify: `npm view @vantio/cli version` should return `0.3.0` after a successful run.

**Everything else in the CLI works correctly** — `vantio run node agent.js` (the actual
Tier 1 free-tier value, no login required) was tested live in this session against the
currently-published 0.1.0 build and intercepted a real outbound call correctly (host, PID,
bytes, timestamp all accurate). The core product isn't broken. The account-linking layer
added in 0.2.0–0.3.0 has simply never shipped to real users.

---

## PyPI (`vantio-agent-sdk`) — HEALTHY. No bug found.

Checked the live PyPI page and tested a real install end to end:

```bash
python3 -m venv test-env && test-env/bin/pip install vantio-agent-sdk
# Successfully installed vantio-agent-sdk-3.0.0
```

Ran the exact README usage example (`@shield` decorator) — worked correctly on first try.
PyPI's published version (3.0.0) matches local `pyproject.toml` exactly. The README shown
on PyPI matches the real, current API. No drift, no discrepancy.

**One real environment note, not a package bug:** `pip install --user vantio-agent-sdk`
fails on modern Debian/Ubuntu with `error: externally-managed-environment` (PEP 668) unless
the user creates a venv or uses `pipx`. This is now default behavior on Ubuntu 23.04+ and
will affect a meaningful fraction of Linux users. **Recommend adding a one-line callout** to
the Python install instructions: "On Ubuntu/Debian, use a virtualenv or `pipx install
vantio-agent-sdk` — modern distros block global pip installs by default (PEP 668)."

---

## GitHub README — accurate to source, but describes what's not actually shippable yet

The README's quickstart is written correctly for the *current source* (0.3.0). It is not
wrong on its own terms. It just documents commands that don't exist in what a real user
downloads, because the publish pipeline silently stopped shipping updates. Once the npm
publish is fixed (see above), the README becomes accurate again with zero further changes.

---

## Summary

| Path | Status | Root cause | Fix owner |
|---|---|---|---|
| `npm install -g @vantio/cli` | Broken for `login`/`logout`/`whoami`/`discover`; core `run` works | Registry stuck at 0.1.0 for a month; CI silently no-op'd on every subsequent push | **Human** — rotate `NPM_TOKEN`, re-run workflow |
| `pip install vantio-agent-sdk` | Healthy | None found | — |
| GitHub README | Accurate to source | Downstream symptom of npm publish failure | Resolves automatically once npm is fixed |

This is very likely the majority of "downloads failed for our users" — the very first
command in the public quickstart, copy-pasted exactly as written, fails unconditionally
for every single user who has ever tried it since the README was updated to describe 0.3.0.
