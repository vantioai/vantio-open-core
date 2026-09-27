# Release discipline

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INTERNAL_RESTRICTED`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Name the release controls that already exist in this repository so a later internal note can point at them. This file does not authorize a release and does not restate release commands.

## Controls to re-read

| Control | Path | What a later note may say |
| --- | --- | --- |
| Documentation release checks | `docs/scripts/check-docs-release.mjs` | The checker compares canonical docs, versions, exports, and the frozen stale-name inventory. |
| Checker plan | `docs/governance/RELEASE-GATE-INTEGRATION-PLAN.md` | At base commit `5064f32f1cdfcb840dfd100e2ce5c712d046550d`, `.github/workflows/ci.yml` does not invoke `docs/scripts/check-docs-release.mjs`. Re-read both files before claiming the checker gates every merge. |
| Version record | `docs/governance/VERSION-METADATA.json` | Tree versions. Documentation edits do not bump them. |
| Package release tooling | `scripts/release/` | Exists. Procedures, tokens, and publish steps stay in that tooling. They are not copied here. |
| Public manual version split | `docs/products/optics/VERSION-METADATA.json` | CLI 0.3.24 matches the recorded npm package. Python source 3.1.0 is not the recorded PyPI package 3.0.14. |

## This room's own rule

A documentation scaffold merge is not a package release. It does not tag, publish, or seal.

## Sections still empty

| Section | Value |
| --- | --- |
| Who may publish | `NOT_FILLED` |
| Rollback narrative for investors | `NOT_FILLED`. Public uninstall notes live in `docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md`. |
| Provenance claim | `NOT_FILLED`. Do not assert a certification or a provenance level from a workflow filename. |
| Company operating runbook | Prohibited in this room |

## Fill rules

- Point at the control. Do not paste scripts, tokens, or registry credentials.
- State the package version beside any "current release" sentence.
- Leave Phantom Engine release mechanics in that repository.
