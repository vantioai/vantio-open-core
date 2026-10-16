# T0 risk register

Label for the track: Lab-only. The live gateway was not measured.
`merge_state`: draft. Do not merge. Do not apply the founder-approved label.

| Id | Risk | Label | What remains |
| --- | --- | --- | --- |
| R1 | Phantom-Box may still be running an image pulled before 2026.1.29, because the start script does not refresh a present image. | Lab-only | Read-only procedure. Affected stays unknown until that output exists. |
| R2 | GHCR `latest` today is patched `2026.10.4` and can move again. The committed default is still the floating tag. | Verified for the tag we resolved. The file edit is an approval gate. | `security/openclaw/patch-spec.json` |
| R3 | `openclaw.json` on the container volume can name skills that are not in git. | Lab-only | `openclaw plugins list` and `openclaw skills list` in the procedure. |
| R4 | Marketplace skill id `clawhub` collides with the image-bundled client. | Verified as a name collision in the cheap-unlocks script. No marketplace copy was found in git. | Checker denies a marketplace source for that id. |
| R5 | `cursor-cli` install command has no version. The recorded commit is v0.0.6. The bytes inside the container were not hashed. | Lab-only for the live plugin. Verified for the git commit and `package.json` sha256 we fetched. | Gated reinstall from that commit after `sha256sum -c`. |
| R6 | `npx -y` without a version can fetch a later filesystem MCP server. | Verified as an unpinned command in `plane1_openclaw_cheap_unlocks.sh`. | Pin `@1.0.0` and its integrity. Applying it is gated. |
| R7 | `vantio-enterprise` was not byte-scanned. Coverage is the compose files, the OpenClaw-named scripts, the runbook, twelve skill bodies, and `agent-hands/skills/plane1-openclaw.md`. | Verified for those blobs. | A later full-tree walk can still find another image reference. The patch script aborts if the expected occurrence count is wrong. |
| R8 | `vantio-enterprise-private` and `vantio-deploy` were listed, not fully walked. Code search missed `plane1-openclaw` and is not evidence of absence. | Lab-only for those two trees. | Another pass with a local clone. |
| R9 | Editing compose does not restart the gateway. Recreate does. An upgrade from a patched 2026.6.34 image to 2026.10.4 is a restart and is not required to clear the CVE. | Approval gate | Restart block stays separate. |
| R10 | Gateway token may already have been exposed if a pre-fix Control UI was opened. | Unknown | Rotate only inside the restart gate, and only when the read-only result says affected. |
| R11 | The Optics hook helper stays fail-open when `VANTIO_HOOKS` is unset. That is the existing observe behavior. This track hashes the file and does not change it. | Verified hash of the current file. | A later enforce change is out of scope. |
| R12 | CI checks this repository and the pin spec. It does not prove the host applied the spec. | Verified for CI scope. | Host evidence is a future artifact, not this proof file. |

## Dependencies

No other gap track. Host steps depend on a founder on Phantom-Box. This branch does not change Phantom Engine, enrollment, or the public installer pin.

## Rollback

Repository: revert this branch. Host file pin: replace the digest with the image id saved before the edit, or restore the five files from commit `59002fb5df244702b1df344c1258839f9b8a3d6b`. Host recreate: `OPENCLAW_IMAGE` set to the saved image id, then compose up. Do not roll back to `:latest`.
