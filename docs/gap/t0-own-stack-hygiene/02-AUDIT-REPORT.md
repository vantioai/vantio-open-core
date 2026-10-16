# T0 audit report

Generated from the reads in `00-DESIGN.md`. Checker: `scripts/gap/t0_openclaw_hygiene.py`.
Label: **Lab-only** for the live gateway. **Verified** for the git blobs and the registry digests named in `security/openclaw/pin.json`.
Time of the registry read: 2026-10-16T15:49:13Z.

## OpenClaw version

| Place | Version | Affected by CVE-2026-25253 |
| --- | --- | --- |
| `vantio-enterprise` Plane 1 compose, start script, desktop probe, legacy `openclaw-gateway` profile, and the Plane 1 runbook | floating tag `ghcr.io/openclaw/openclaw:latest` | Unknown. A floating tag is not a version. |
| GHCR tag `latest` and tag `2026.10.4` on 2026-10-16 | `2026.10.4`, index digest `sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a` | No. The fix line is 2026.1.29. |
| Runbook statement that the 2026.6.34 ACP CLI is present | `2026.6.34` if that sentence still matches the binary. Index digest `sha256:47d342bafe83bd3b2dca6f1d8d8b608ba7b542a1952564960648943346206759` | No, if the binary is actually 2026.6.34 or newer. Not Verified. |
| Phantom-Box container `vantio-plane1-openclaw` | Not measured. This environment cannot reach the host. `start_plane1_openclaw.sh` pulls only when the local image is missing. | Unknown until `03-PHANTOM-BOX-PROCEDURE.md` is run. |

npm package in the GitHub advisory is `clawdbot`, fixed at 2026.1.29. The current published name is `openclaw`. `clawdbot@2026.1.29` is not on the registry. The pin uses `openclaw@2026.10.4` integrity `sha512-+FH0StZF1tlTazM7JJGY6JePeJmhFNSRByi2Q3jXPRiLO7o4dJh2xa9Vy4Dk8Cd2ic8B7Zkf5NfEaCCWUkgqnQ==` and shasum `ac000cc196b31208b0108c171780a3312ea26e5e`.

`vantio-open-core` does not install OpenClaw. `vantio-phantom-engine` `Dockerfile` builds `vantio-loader`, not OpenClaw. `vantio-enterprise-private` root and `docs/` have no OpenClaw path. `vantio-deploy` `manifests/artifacts.json` has no OpenClaw image. The public installer pin prefix `e0b19d55` is unchanged.

## Patch

The CVE patch is OpenClaw 2026.1.29 or newer. The repository pin this track records is the 2026.10.4 index digest above, written as `ghcr.io/openclaw/openclaw@sha256:614004ec2cf2e6095124ea544dc8d950c49306aef445a1fc300b88717e24261a`.

`security/openclaw/patch-spec.json` replaces `ghcr.io/openclaw/openclaw:latest` in these `vantio-enterprise` blobs at commit `59002fb5df244702b1df344c1258839f9b8a3d6b`:

| Path | Blob | Occurrences |
| --- | --- | --- |
| `plane1-openclaw/docker-compose.yml` | `9de238e56427f905aab88a29a37b5154f5b454c6` | 1 |
| `scripts/start_plane1_openclaw.sh` | `1c9e3c24dfca1de611fe52bc5d68fa21a5d32061` | 1 |
| `scripts/plane1_openclaw_desktop_enable.sh` | `c96294fb978b96299c0da8c78dc8a45ecac4a577` | 1 |
| `agent-hands/docker-compose.yml` | `601a59f3093f0cb040281d1360b7bcf2d3348a03` | 2 |
| `docs/ops/OPENCLAW_PLANE1_PHANTOM_BOX.md` | `dd4a9098b4dbe3c5cce121703b4c0b006a5eb7ed` | 2 |

Those files are not edited in `vantio-enterprise` by this branch. Applying the replacement on Phantom-Box is an approval gate and does not by itself restart the container. A pull or recreate is a second gate.

Install pins, also gated:

| Id | Required pin |
| --- | --- |
| `cursor-cli` | git `ee2fc0c57d39dd65e3cbc260a3a43f319a74ece9`, `package.json` sha256 `8963a59dcf32e532344d053ae4f58f5d292f5021d86513d513f63027351e4ef6` |
| `googlechat` | `@openclaw/googlechat@2026.10.4`, integrity `sha512-Og+HTkRAoD5UcPsQVmneuELVS5GOCJLjd56yF4ncnmS/bTnK0zxV6q/aCNkU+9wP69n+dcM7WXxOa4//rf3geA==` |
| `plane1-fs-proof` | `@modelcontextprotocol/server-filesystem@1.0.0`, integrity `sha512-2fN6qhpsiPSBAe0ev1qDPk4sCWdULCZQTuYc4ZY7+BDWQ1XCxLB+7dqStF2ZflgG4G/9vTwQsjxh7pjFqrrpcg==` |

## Allow-list and ClawHavoc

No allow-list existed in `vantio-open-core`. `security/openclaw/allowlist.json` is the new one.

OpenClaw config names `cursor-cli`, `browser`, `googlechat`, `cua-computer`, bundled skills `healthcheck`, `taskflow`, `taskflow-inbox-triage`, `browser-automation`, `weather`, `skill-creator`, and `clawhub`, plus MCP `plane1-fs-proof`. In-repo hooks are the Cursor and Claude Code examples and `integrations/hooks/lib/maybe-vantio-run.mjs`. The OpenClaw file under `integrations/hooks/` is an example, not an installed plugin.

`clawhub` is allow-listed only as an image-bundled skill. A marketplace install of `clawhub` or `clawdhub1` fails the checker. Publisher `jeehou` is not in the campaign publisher set. The twelve `vantio-enterprise` `skills/*/SKILL.md` bodies are ops pointers, not ClawHub packages. None of those bodies contained a campaign indicator. Their git blobs are on the allow-list so a later edit has a recorded identity.

The live `openclaw.json` is on the container volume and was not read. Skills installed only there stay unknown.

## CI

`.github/workflows/t0-own-stack-hygiene.yml` runs the unit tests and `python3 scripts/gap/t0_proof.py --check`. The checker fails closed on a missing pin, a floating or affected image reference in an install-shaped file in this repository, a digest other than the pin, an allow-list hash mismatch, a blocked publisher, or a campaign indicator in an allow-list field or install-shaped file. It does not download the image.
