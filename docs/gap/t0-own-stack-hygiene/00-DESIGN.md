# T0 own-stack hygiene — design

Track: T0 of the October 2026 market-readiness gap program.
Author: this agent (Grok 4.7).
Written: 2026-10-16T15:49:13Z.
Status: design only. No checker, pin file, or workflow exists in this commit.
Label of this packet: Lab-only for the live gateway. Verified for the git reads and registry lookups named below.

This packet is the phase-1 boundary check. It is not a claim that the live Phantom-Box gateway was measured, and it is not the different-family review of the final commits.

## Question

Where do Vantio repositories pin, install, or configure OpenClaw, what version is that relative to CVE-2026-25253, which skills, plugins, and hooks does that configuration name, and how do we pin those versions and check hashes without restarting Phantom-Box?

## Threat model

Two public problems, kept separate.

CVE-2026-25253 (GHSA-g8p2-7wf7-98mq, published 2026-02-02T23:41:05Z, CVSS 3.1 8.8 `AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H`). OpenClaw, also shipped as clawdbot and Moltbot, before 2026.1.29 reads `gatewayUrl` from the Control UI query string and opens a WebSocket without a confirmation prompt, sending the stored gateway token. A browser visit is enough. Loopback bind does not stop it, because the victim's browser makes the outbound connection. The attacker then holds operator access on the gateway. GitHub's reviewed advisory fixes npm package `clawdbot` at 2026.1.29 (affected `<= 2026.1.28`). The CVE record says the product is affected before 2026.1.29. The fix commit named by the advisory is `a7534dc22382c42465f3676724536a014ce0cbf7`. OSV names git fix `77e703c69b07a236c2f0962bd195e03aae1b8da0`, which is the image revision label on tag `2026.1.29`.

ClawHavoc is a marketplace campaign, not that CVE. Public write-ups (Snyk, 2026-02-02; Koi's checks as encoded by oakencore/skillvet; PolySwarm) describe malicious ClawHub skills that ask the operator to run a downloader. Indicators used by the checker, stored raw only in the indicator file:

- IPv4 `91.92.242.30` and `54.91.154.110`
- host `download.setup-service.com`, `openclawcli.vercel.app`, and `clawhavoc.net`
- URL path `glot.io/snippets/hfd3x9ueu5`
- repository `Ddoy233/openclawcli`
- publishers `zaycv`, `Ddoy233`, `hightower6eu`, `moonshine-100rze`
- marketplace skill ids `clawhub` and `clawdhub1` when the source is a marketplace install rather than the image-bundled client
- password-protected archive instructions that use the password `openclaw`
- base64 piped into a shell, and `xattr -c` followed by execute

A skill whose only crime is the name `clawhub` inside the official image is a name collision, not a hit. A marketplace install of that name is a hit.

## What was read

Reads happened through the GitHub contents API. This environment's git credential can clone `vantio-open-core` and cannot clone the private repositories (`repository not found` without that API). GitHub code search is not evidence of absence: an organization query for `openclaw` returned eight hits and `incomplete_results: false`, and still omitted `vantio-enterprise/plane1-openclaw/docker-compose.yml`, which the contents API then returned.

| Repository | Commit read | OpenClaw install or pin |
| --- | --- | --- |
| `vantio-open-core` | `69671e97fa359b685232ec7dd4e9fb4badc7be57` | No image, npm dependency, or running gateway. Hook sketch at `integrations/hooks/openclaw-plugin.example.md`. Cursor and Claude Code hook examples call `integrations/hooks/lib/maybe-vantio-run.mjs`. Ingress fixtures use the workload name `openclaw` and do not install it. |
| `vantio-enterprise` | `59002fb5df244702b1df344c1258839f9b8a3d6b` | Plane 1 gateway. Image default `ghcr.io/openclaw/openclaw:latest` in `plane1-openclaw/docker-compose.yml` (blob `9de238e56427f905aab88a29a37b5154f5b454c6`), `scripts/start_plane1_openclaw.sh` (blob `1c9e3c24dfca1de611fe52bc5d68fa21a5d32061`), and `scripts/plane1_openclaw_desktop_enable.sh` (blob `c96294fb978b96299c0da8c78dc8a45ecac4a577`). Legacy opt-in profile `openclaw-gateway` in `agent-hands/docker-compose.yml` (blob `601a59f3093f0cb040281d1360b7bcf2d3348a03`) uses the same floating default. Runbook `docs/ops/OPENCLAW_PLANE1_PHANTOM_BOX.md` (blob `dd4a9098b4dbe3c5cce121703b4c0b006a5eb7ed`) tells the operator to set `OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest`. |
| `vantio-enterprise-private` | `c9dc0604649140bff5e593524ff116518bcfe7de` | No OpenClaw path in the repository root or under `docs/`. Not a full-tree byte scan. |
| `vantio-phantom-engine` | `deb6faa33e5cbb887622df5017ce74d2571fa9e8` | No OpenClaw image. `Dockerfile` builds `vantio-loader`. Docs and `python/pe_ingress_truth.py` name OpenClaw as a workload the engine may observe. `deploy/` is gate-onprem, helm, and kubernetes for Phantom Engine. |
| `vantio-deploy` | `b874411667d2262391f41eb478b3669459839f21` | `manifests/artifacts.json` (blob `743b432dcab363ef1362f3c1eba917a2dac4e5fa`) has no OpenClaw image. Public installer pin prefix stays `e0b19d55`. This track does not edit that manifest. Terraform roots were not walked file by file. |

## Version evidence

Registry lookup at 2026-10-16T15:49:13Z, anonymous GHCR pull token, no image pull onto a Vantio host:

| Tag | Index digest | `org.opencontainers.image.version` | Created |
| --- | --- | --- | --- |
| `latest` | `sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a` | `2026.10.4` | 2026-10-15T17:23:32Z |
| `2026.10.4` | same digest as `latest` | `2026.10.4` | same |
| `2026.6.34` | `sha256:47d342bafe83bd3b2dca6f1d8d8b608ba7b542a1952564960648943346206759` | `2026.6.34` | 2026-08-04T14:08:41Z |
| `2026.1.29` | `sha256:7b67c341d87f8e954dc1e8e9d7bb3aaeaf36acd49594abe4adb826ee89107170` | `2026.1.29` | 2026-01-30T05:27:21Z |

linux/amd64 manifest for `2026.10.4` is `sha256:07091f4b3fef9b56f3b6f5d556a2a48cea7ac9d4b3634235c1eccc15f5cf91ed`. Config blob `sha256:1500f1058cec475b9f2d2725554aed424ed136533071016f3734fd772aadc695`. Revision `383c124cc32ffee3f8e56f549b88da94d269a4af`.

npm `openclaw@2026.10.4` integrity `sha512-+FH0StZF1tlTazM7JJGY6JePeJmhFNSRByi2Q3jXPRiLO7o4dJh2xa9Vy4Dk8Cd2ic8B7Zkf5NfEaCCWUkgqnQ==`, shasum `ac000cc196b31208b0108c171780a3312ea26e5e`. npm `openclaw@2026.1.29` is the first release at the fix line. npm `clawdbot@2026.1.29` returns 404; the advisory name and the current package name differ. The checker treats both names as the same product.

The committed install does not select any of those digests. `start_plane1_openclaw.sh` pulls only when the local image is missing, then leaves a running container alone. So today's `latest` digest is not the version on Phantom-Box until someone pulls.

The runbook row for the ACP bridge says the feature is built into the OpenClaw 2026.6.34 CLI and that the Phantom-Box status is Present (runbook updated 2026-08-09). That is a documentation claim, not an `openclaw --version` capture. 2026.6.34 is after 2026.1.29, so that claim, if it still matches the running binary, means CVE-2026-25253 is already patched on the box. It does not authorize calling the live version Verified.

Disposition until the read-only host commands run: version unknown, affected unknown. The git default can still resolve to an affected image if the host pulled `latest` before 2026-01-30 and never pulled again, or if a later retag moves `latest`. The registry tag `latest` observed today points at a patched build.

## Skills, plugins, and hooks named by config

No in-house OpenClaw allow-list exists in `vantio-open-core`. The implementation creates one.

OpenClaw plugins and skills named by enterprise scripts and the runbook, not by a committed `openclaw.json` (that file lives in the container volume):

| Id | Kind | Where named | Pin today |
| --- | --- | --- | --- |
| `cursor-cli` | plugin | runbook install `clawhub:@jeehou/openclaw-cursor-cli`, documented v0.0.6; `plane1-openclaw/config/cursor-cli-shell-privilege.raise.json5` | git commit `ee2fc0c57d39dd65e3cbc260a3a43f319a74ece9`; `package.json` sha256 `8963a59dcf32e532344d053ae4f58f5d292f5021d86513d513f63027351e4ef6`. Install command does not pass a version. Publisher `jeehou` is not in the ClawHavoc publisher set. |
| `browser` | plugin | `scripts/plane1_openclaw_browser_enable.sh` writes `plugins.allow` | bundled in the image; no separate package |
| `googlechat` | plugin | `scripts/plane1_googlechat_enable.sh` runs `openclaw plugins install @openclaw/googlechat` | unpinned. npm `@openclaw/googlechat@2026.10.4` integrity `sha512-Og+HTkRAoD5UcPsQVmneuELVS5GOCJLjd56yF4ncnmS/bTnK0zxV6q/aCNkU+9wP69n+dcM7WXxOa4//rf3geA==`. The 2026.6.34 release of that package also exists. |
| `cua-computer` | plugin | `scripts/plane1_openclaw_desktop_enable.sh` enables it only if the image ships it, and records an attempted `@openclaw/cua-computer` install that the script itself expects to fail | not an allowed install from npm |
| `healthcheck`, `taskflow`, `taskflow-inbox-triage`, `browser-automation`, `weather`, `skill-creator` | skill | `scripts/plane1_openclaw_cheap_unlocks.sh` lists them as bundled | image-bundled; hash is the image digest |
| `clawhub` | skill | same script, bundled client | name collision with the malicious marketplace skill. Allowed only as image-bundled. Marketplace install of `clawhub` or `clawdhub1` is denied. |
| `plane1-fs-proof` | mcp | same script: `npx -y @modelcontextprotocol/server-filesystem` | unpinned `npx -y`. npm `@modelcontextprotocol/server-filesystem@1.0.0` integrity `sha512-2fN6qhpsiPSBAe0ev1qDPk4sCWdULCZQTuYc4ZY7+BDWQ1XCxLB+7dqStF2ZflgG4G/9vTwQsjxh7pjFqrrpcg==` |

Hooks in this repository:

| Id | File |
| --- | --- |
| `cursor-before-shell` | `integrations/hooks/cursor-hooks.json` |
| `claude-pre-tool-bash` | `integrations/hooks/claude-code-settings.example.json` |
| `openclaw-optics-sketch` | `integrations/hooks/openclaw-plugin.example.md` (example, not an installed plugin) |
| helper | `integrations/hooks/lib/maybe-vantio-run.mjs` |

Enterprise `skills/*/SKILL.md` (twelve files, blobs recorded in the implementation inventory) are ops pointer contracts for department loops. They are not ClawHub packages and they are not referenced by `openclaw.json`. None of the twelve bodies contained a ClawHavoc network indicator or publisher. `agent-hands/skills/plane1-openclaw.md` is an extracted pulse note, not a marketplace skill. `agent-hands/skills/proof-skill-injection-test.md` is a prompt-injection mechanism fixture and is out of scope for this track's allow-list except as a named non-OpenClaw file.

## Boundary

In scope: record the pin, hash-check it, allow-list the names above, scan those records and this repository's install-shaped files for the indicators, add a CI job, and write the Phantom-Box commands.

Out of scope, and unchanged by the later commits: Phantom Engine behavior, enrollment, public installer pin `e0b19d55`, public README and product claims, prices, IAM, production signing, GHCR publishes, and any start, stop, pull, or recreate of `vantio-plane1-openclaw`.

Fail closed. A missing pin file, an unparseable version, a floating tag in an install-shaped file in this repository, a version below 2026.1.29, a digest that is not the recorded index digest, an allow-list miss, a marketplace `clawhub` or `clawdhub1` entry, or a ClawHavoc indicator in an allow-list field exits non-zero. The checker does not treat "search index returned nothing" as clean.

Fail open is rejected. A hygiene check that skips unknown files or accepts `:latest` because the registry happens to be patched today would hide the next retag.

Version compare is numeric CalVer, not lexicographic. The string `2026.10.4` sorts before `2026.6.34` as text and after it as a version. Prereleases sort before the matching release, so `2026.1.29-beta.1` is below the GHSA fix line `2026.1.29` even though Snyk's openclaw note mentions the beta. That is the stricter rule.

Memory. One short-lived Python process reads the pin files and walks this repository. It does not start a gateway, a container, or a resident agent. It skips nothing silently: oversized files are a failure, not a pass.

eBPF verifier limits do not apply. This track does not load a program.

Rollback of the repository change is `git revert` of the track commits. No host rollback exists until the approval gate runs, and the gate's first command records the current image id so a later recreate can return to that id. The procedure must not use `:latest` as the rollback target.

Phantom-Box. This agent cannot reach the host. Read-only commands and the patch procedure are documents. Applying them, including any `docker pull` or compose recreate, is an approval-gate item. `plane1_openclaw_desktop_enable.sh` `cua-probe` pulls `:latest`; the read-only procedure forbids that mode.

## Implementation that may follow this commit

Only after this design and its verdict are committed:

- `security/openclaw/pin.json` — image index digest, amd64 manifest digest, npm integrity, fix floor `2026.1.29`
- `security/openclaw/allowlist.json` — the rows above, with hashes where a hash was retrieved
- `security/openclaw/indicators.json` — the raw indicators
- `security/openclaw/inventory.json` — repo, path, blob, and the floating ref
- `security/openclaw/patch-spec.json` — exact string replacement from the floating ref to `ghcr.io/openclaw/openclaw@sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a`
- `scripts/gap/t0_openclaw_hygiene.py` — the checker
- `scripts/gap/t0_proof.py` — writes the evidence artifact
- `tests/gap/test_t0_openclaw_hygiene.py`
- `.github/workflows/t0-own-stack-hygiene.yml`
- audit report, Phantom-Box procedure, risk register
- evidence artifact produced by the proof script

The patch spec is the pin for the enterprise files. It is not applied to `vantio-enterprise` from this environment, and it is not applied on the host.

## Dependencies

No other gap track. Host application depends on a founder running the procedure on Phantom-Box. Live `openclaw skills list` can still show plugins that were installed only in the volume; those stay Lab-only until that command's output is stored.
