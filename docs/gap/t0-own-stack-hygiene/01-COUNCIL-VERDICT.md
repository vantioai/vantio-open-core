# T0 phase-1 council verdict

Date: 2026-10-16T15:49:13Z
Subject: `docs/gap/t0-own-stack-hygiene/00-DESIGN.md` only. No product code is in this commit.
Council: phase-1 design review by the authoring model (Grok 4.7).
This is not the different-family review. That review waits until the final commit and has to read that head, not this design.

## Verdict

`PASS_TO_IMPLEMENT`

The design may be implemented inside the constraints below. It does not authorize a Phantom-Box change, a merge, or a founder-approved label.

## Checks

| Boundary | Result |
| --- | --- |
| Threat model names CVE-2026-25253 and ClawHavoc as different problems, with the advisory's fix line | Pass |
| Live gateway version is unknown, so "affected" stays unknown until read-only host output exists | Pass |
| Floating `:latest` is the defect even when today's registry tag is patched | Pass |
| Fail closed on missing pin, bad version, floating install ref, allow-list miss, and indicator hit | Pass |
| Version compare is numeric, and prerelease `2026.1.29-beta.1` stays below `2026.1.29` | Pass |
| No proxy hop, no new permission, no conversation store | Pass |
| Phantom Engine scope is not widened | Pass |
| No price, no secret, no public pin edit, no README claim edit | Pass |
| Rollback of the repo is revert; host rollback captures the current image id before any pull | Pass |
| Applying the pin on Phantom-Box is an approval gate and includes no restart by this agent | Pass |
| Code search absence is not treated as a clean repo | Pass |

## Constraints on the implementation

1. Do not edit `vantio-enterprise`, `vantio-phantom-engine`, `vantio-enterprise-private`, or `vantio-deploy` from this branch. The pin for those trees is `security/openclaw/patch-spec.json` plus the host procedure.
2. Do not `docker pull`, compose up, or restart anything. The desktop script's `cua-probe` pull is forbidden in the read-only procedure.
3. The desired image pin is the index digest recorded for `2026.10.4`, which is the digest `latest` resolved to on 2026-10-16. Do not pin the mutable tag `latest`.
4. Marketplace skill ids `clawhub` and `clawdhub1` are denied. The bundled skill id `clawhub` is allowed only with source `image-bundled`.
5. Hash checks compare stored digests. They do not download the image in CI.
6. The evidence artifact is the proof script's output. A hand-written JSON file does not count.
7. Label the live host Lab-only. Label the git reads and the registry lookup Verified only for the commits and digests named in the design.
8. Leave the public installer pin prefix `e0b19d55` untouched.

## Residual the implementation must keep visible

`vantio-enterprise` was not byte-scanned. Coverage is the compose files, the OpenClaw-named scripts, the runbook, the twelve `skills/*/SKILL.md` bodies, and `agent-hands/skills/plane1-openclaw.md`. A skill installed only inside the gateway volume is invisible until the host command runs.

`vantio-enterprise-private` and `vantio-deploy` were listed at the root and at the paths named in the design, not walked as full trees.

## Result line

`council_pass`: true for implementation of this design.
`merge_state`: draft only. Do not merge.
`reviewer_family`: Grok, same family as the author. Final head still needs a different family.
