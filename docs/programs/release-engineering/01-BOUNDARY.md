# WS11 boundary

Audience: INTERNAL_RESTRICTED

Producer: Cursor cloud agent `bc-b0d40632-9601-5475-9941-b2aab0f4b75d`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-b0d40632-9601-5475-9941-b2aab0f4b75d

Producer classification: `WS11_RELEASE_ENGINEERING_REVISION_READY_FOR_COUNCIL`

Council `bc-6ad40712-8957-5742-b9a4-b42fecf3b115` returned `WS11_RELEASE_ENGINEERING_NEEDS_REVISION` on tip `2e20cb018590dff720e2c209ad2b41ee2b9a0035`. This revision closes the Phantom R13 distribution hole and is ready for a separate council. `council_pass` is false. `04-INDEPENDENT-COUNCIL.md` stays `PENDING_INDEPENDENT_COUNCIL`.

## What this force implements

A release dossier format and an independent verifier for three surfaces: Optics, Phantom Engine, and the private customer package. The verifier evaluates R1–R18 and prints `release_success` true only when every requirement is `SATISFIED` and the requested disposition is `READY_TO_PUBLISH` or `EMERGENCY`. The dossiers committed for the current tree request `CHARACTERIZED`. Their result is `release_success` false.

Claim tokens on the manifest, the pin report, the SBOM, and every verifier result:

| Token | Value |
| --- | --- |
| `formal_slsa_level` | `NOT_CLAIMED` |
| `formal_certification` | `NOT_CLAIMED` |
| `formal_reproducibility` | `NOT_CLAIMED` |
| `hardware_backed_provenance` | `NOT_CLAIMED` |

A dossier string that matches the denylist in `REQUIREMENTS.json` is `REJECTED`. A two-digest match can satisfy R2 and still leaves `formal_reproducibility` at `NOT_CLAIMED`.

## What this force keeps closed

- `@vantio/cli` stays `0.3.24`. This force does not patch, pack, retag, or publish it.
- `vantio-agent-sdk` `3.1.0` source and the sealed hash pins stay as they are. This force does not rebuild or upload those bytes.
- No npm, PyPI, MCP registry, or GHCR write. No new publish workflow.
- No customer deploy, no stranger-host execution, no announcement, no credential creation.
- No Phantom Engine customer-manual body in this public tree. The test double remains a test double.
- No merge. The pull request stays draft.
- `docs/programs/production-readiness/WORKSTREAM-REGISTRY.json` stays the prior snapshot.

## How to read a green verifier exit

Exit 0 on a current dossier means the dossier is well formed and characterized, gaps included. It is not a release. Exit 2 means a publish request is missing evidence or the publication is partial. Exit 1 means the dossier is rejected, including overclaims and hash mismatches.
