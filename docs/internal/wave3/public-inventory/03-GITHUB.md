# GitHub

Audience: INTERNAL_RESTRICTED

Org `vantioai` (display name Vantio AI Inc) is unverified. Public repository count is 4. Blog `https://vantio.ai`. Email `hello@vantio.ai`. Location Pittsburgh. `twitter_username` is null.

Org description, which is an org setting rather than a file in this repository:

> Pittsburgh, 2026. Optics helps you see. Gate applies the rules you set. Phantom Engine protects the machines you own. Blind by design. Not a proxy.

The public profile README in `vantioai/.github` describes three products, prices Phantom Engine at $799 per node per month, and links `vantioai/vantio-phantom-engine`. That repository URL returned HTTP 404 to this token and is not in the public list. The same 404 was returned for `vantio-pro`, `vantio-app`, `vantio-vos`, `vantio-revenue-engine`, and the website-shaped names that were probed. HTTP 404 does not distinguish missing from inaccessible.

Public member listed: `zacharybalicki` (profile name VantioAi, company Vantio AI, Inc., blog vantio.ai, no Twitter field). That user’s two public repositories are forks of MCP server lists, not product source.

## vantio-open-core

Description still says `@vantio/cli 0.3.2` and `vantio-agent-sdk 3.0.2`. Homepage `https://vantio.ai/optics`. Topics include `sight-loop` and `governance`. The license API field is null, and there is no root `LICENSE` file. Package files declare MIT.

Absent: `SECURITY.md`, code of conduct, issue templates, pull request template, root `llms.txt`. Present: `CONTRIBUTING.md`.

Public workflows, not dispatched by this track: `ci.yml`, `docs-release-governance.yml`, `enterprise-slsa-provenance.yml`, `mcp-registry-publish.yml`, `npm-publish.yml`, `pypi-publish.yml`, `vantio-prove-example.yml`.

Releases:

| Tag | Published | Assets |
| --- | --- | --- |
| `custody-py-3.1.0` | 2026-09-27 | wheel and sdist; SHA-256 matches PyPI 3.1.0 |
| `v0.3.24` | 2026-09-26 | none |
| `v0.3.23`, `v0.3.22`, `v0.3.21` | 2026-09-25 to 2026-09-26 | none |

Other tags: `pre-autonomy-rebuild-v1`. The release body for `custody-py-3.1.0` calls itself an internal custody placement.

Open issue #3 is titled “MCP marketplace listings — Optics.” The API open-issue count of 6 includes pull requests.

Reader-facing paths on this tip include the root README, `architecture_state.md`, `docs/PRODUCT_LINEUP.md`, `docs/products/optics/`, the package READMEs, both MCP `server.json` files, and `extensions/vantio-optics/README.md`. `.env.example` is public and contains placeholder names for Supabase, Stripe, Upstash, Calendly, Slack, and Resend. The values are placeholders.

`packages/vantio-gate-mcp/server.json` is public. Its title says Gate is a legacy package name and not a separate product. It documents a default API base of `https://api.vantio.ai`. That hostname did not resolve during this inventory.

`docs/products/optics/` is manual version 1, status `draft-honest`, registry check inside the file at 2026-09-27T05:24:00Z. That manual says PyPI is 3.0.14 and that Python 3.1.0 is unpublished. No PDF was generated. This track did not edit the manual.

There are 85 public branches, listed in the JSON. One branch name is `xPH6HTem4Is3qmtW`. Its tip is a merge commit about registry visibility polling (`04b8d944494a477ea53c56c524aa247c5260a80c`, 2026-09-26). The name is public. The branch was not expanded beyond that tip.

A ripgrep of this checkout found 200 files containing “Phantom Engine.” Those files were not quoted one by one.

## .github

Files are `README.md` and `profile/README.md`. A second public branch is `track2/org-profile-disclosure-remediation` (tip `a4e1cae0`, 2026-09-20). Four open issues still title Gate as Policy Latch and Phantom Engine as Bypass Reconciliation, plus a website brand-system issue and an Optics Sight Loop issue.

## vantio-optics-cursor-plugin

Observe-only Cursor plugin. Homepage `https://vantio.ai/optics`. README points marketplace submitters at `cursor.com/marketplace/publish` and `cursor.directory/mcp/new`, with logotype `https://vantio.ai/vantio-logo.png` (HTTP 200). It says Smithery’s hosted-URL flow does not fit a local stdio server. It also says `@vantio/gate-mcp` is a legacy compatibility package and that Gate is not a separate product. Second public branch: `sanitize/skill-customer-safe` (2026-09-20). No releases and no issues.

## autonomous-ops-framework

Default branch `master`. MIT license. README title is “Phantom Box (OSS framework skeleton)” and the status line says “v0 skeleton, not yet announced.” It describes a generic operating pattern and says company-specific data was stripped. No releases, tags, or issues. One public branch.
