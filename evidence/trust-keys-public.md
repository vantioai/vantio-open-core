# Public trust keys

Offline commands only. No workflow dispatch, tag, publish, seal, or signature with a production private key.

## SHA

`code_commit` is the commit the installer suite was re-run against, and the parent of the commit that adds this file:

`01e8963f08b3cc14b19af436cb571070e875a5b0`

Base `main` at the start of the work was `2b8abb4cc75708e2a0c05a7535114cabf95e735e`. The branch head is the commit that adds this file. Its SHA is `git rev-parse HEAD` after that commit and is copied into the pull request. This file cannot contain that commit's own SHA.

The installer suite below was re-run at `code_commit` (exit 0, 288 tests, no skips). The other commands ran on the worktree that became `code_commit`, before the commit object existed. One docstring in `artifact_verify.py` was edited after that broader run and before `code_commit` (`stored` in place of a different verb). Those other commands do not execute that docstring. The docs check in this note was run on the worktree that already contained this file, immediately before the evidence commit.

## Supplied public key files

SHA-256 of each PEM file (the file bytes, not the raw key):

| File | SHA-256 |
| --- | --- |
| `lic-live-2026-10.pub` | `3fa5f9e5e11ad28254a07d7b6ff844ff777c3a6207537f435809d7332c6f52a9` |
| `prod-artifact-2026-11.pub` | `1f57bdc5c98b0162f3139d1841211cde68fa12dedbee20957d188ae7391f458e` |

SHA-256 of each raw 32-byte Ed25519 public key:

| Key id | SHA-256 |
| --- | --- |
| `lic-live-2026-10` | `9ddf4480807c44e963864dafaace202755c21af2acdd6a1f2a887457f69531c5` |
| `prod-artifact-2026-11` | `aea8a06fe3dfd090e3c35e5a4dee6015e5e283ac7b66caf6f14a58f91ae724e4` |

Both PEM files are SubjectPublicKeyInfo Ed25519 public keys (44-byte DER, 32-byte raw key). Loading either file as a private key failed. The text does not contain a private-key marker.

`prod-artifact-2026-11` is the filename `prod-artifact-2026-11.pub` with `.pub` removed. Confirm that id. `lic-live-2026-10` is the filename `lic-live-2026-10.pub` with `.pub` removed.

On `main` at `2b8abb4` both trust files were `{"keys": []}`. They had no schema, `build_mode`, or `revoked_kids` field. This change writes schema 2, `build_mode` `live`, and `revoked_kids` `[]` on the license file.

## Toolchain

- Node.js v22.23.4, package manager `pnpm@11.13.0`
- Python 3.12.3
- `strace 6.8-0ubuntu2` (CLI tests). Candidate from `apt-cache policy strace` was `6.8-0ubuntu2`. `dpkg-query` printed `strace 6.8-0ubuntu2`.
- Installer hashes: `cryptography==46.0.5` from `packages/vantio-install/requirements/dev-hashes.txt`
- `pyyaml==6.0.1` (already installed; the release-gate workflow pins that version)
- Python SDK observe libraries, from `pip index versions` then an exact install: `requests==2.34.2`, `httpx==0.28.1`, `aiohttp==3.14.5`, `urllib3==2.8.0`

## Commands

Working directory is the repository root unless noted. Exit codes are the process status.

| Command | Exit | Skips |
| --- | --- | --- |
| `python3 -m compileall -q vantio_install` then `python3 -m unittest discover -s tests -t . -v` in `packages/vantio-install`, re-run at `code_commit` | 0 | none. 288 tests, OK |
| `node docs/scripts/check-docs-release.mjs` on the worktree that contains this file | 0 | `ok: true`, `failures: []` |
| `node --test docs/scripts/check-docs-release.test.mjs tests/disclosure-governance-cleanup/direct.test.mjs tests/disclosure-governance-cleanup/adversarial.test.mjs` | 0 | 0 skipped, 23 passed |
| `pnpm --filter @vantio/cli run lint` | 0 | syntax check, no test count |
| `pnpm --filter @vantio/cli run test` | 0 | 0 skipped, 175 passed |
| `pnpm --filter @vantio/agent-sdk run typecheck` | 0 | `tsc --noEmit` |
| `pnpm --filter @vantio/agent-sdk run typecheck:test` | 0 | `tsc` |
| `pnpm --filter @vantio/agent-sdk run test` | 0 | 0 skipped, 42 passed |
| `pnpm --filter @vantio/agent-sdk run build` | 0 | `tsc` and postbuild |
| `pnpm --filter @vantio/gate-mcp test` | 0 | 0 skipped, 50 passed |
| `node --test packages/vantio-mcp-awareness/test/*.test.js` | 0 | 0 skipped, 36 passed |
| `node packages/vantio-mcp-awareness/scripts/proof.mjs` | 0 | `assertions=26 failed=0` |
| `python3 -m unittest discover -s tests -t . -v` in `packages/vantio-agent-sdk-py` | 0 | 3 skipped, 126 tests. Skips: `pycurl is not installed`; `pycurl is not installed; its success path stores no HTTP status`; `build is not installed; local verification installs it and does not upload` |
| `node --test scripts/release/governance.test.mjs` | 0 | 0 skipped, 15 passed |
| `node --test scripts/release/ws11/ws11.test.mjs` | 0 | 0 skipped, 14 passed |
| `node --test scripts/release/seal-identity-recheck.test.mjs` | 0 | 0 skipped, 1 passed |
| `node --test scripts/release/engine-archive-rebuild.test.mjs` | 0 | 0 skipped, 3 passed |
| `node --test scripts/release/pe-canonical-seal.test.mjs` | 0 | 0 skipped, 1 passed |
| `python3 scripts/release/test_pe_canonical_seal.py -v` | 0 | 5 tests, no skip line |
| `python3 scripts/release/test_promote_pypi.py -v` | 0 | 8 tests, no skip line |
| `python3 scripts/release/test_pypi_publish_workflow.py -v` | 0 | 1 skipped: `VANTIO_SEALED_DIR is not set`. 19 tests |
| `python3 scripts/release/test_optics_release_observe.py -v` | 0 | 6 tests, no skip line |
| `python3 scripts/aws/test_webshell_grade.py -v` | 0 | 8 tests, no skip line |
| `python3 scripts/aws/test_verify_w3_lab_teardown.py -v` | 0 | 51 tests, no skip line |
| `python3 scripts/aws/test_preflight_w3_lab_teardown.py -v` | 0 | 11 tests, no skip line |
| `python3 scripts/aws/test_w3_lab_teardown_workflow.py -v` | 0 | 5 tests, no skip line |
| `python3 scripts/aws/test_w3_lab_auto.py -v` | 0 | 33 tests, no skip line |
| `python3 scripts/aws/test_w3_lab_steps.py -v` | 0 | 114 tests, no skip line |
| `python3 scripts/lab/test_host_evidence_hu.py -v` | 0 | 18 tests, no skip line |
| `python3 scripts/lab/test_sparse_host_evidence.py -v` | 0 | 1 test, no skip line |
| `python3 scripts/lab/test_hostcheck_rows.py -v` | 0 | 60 tests, no skip line |
| `python3 scripts/gcp/test_gcp_enterprise_uninstall.py -v` | 0 | 33 tests, no skip line |
| `python3 scripts/aws/test_phase2_grade.py -v` | 0 | 1 skipped: `local netns`. 125 tests |
| `python3 scripts/aws/test_descendant_banner.py -v` | 0 | 8 tests, no skip line |
| `python3 scripts/aws/test_lab_oidc_trigger.py -v` | 0 | 11 tests, no skip line |
| `python3 scripts/aws/test_w3_lab_eip.py -v` | 0 | 5 tests, no skip line |
| `python3 scripts/gcp/test_lab_auto.py -v` | 0 | 22 tests, no skip line |
| `python3 scripts/gcp/test_offline_deliver.py -v` | 0 | 1 skipped: `PLACEHOLDER (F7): awaiting a real describe capture of a clean lab VM`. 109 tests |
| `python3 scripts/gcp/test_gcp_2d_restart.py -v` | 0 | 40 tests, no skip line |
| `python3 scripts/gcp/test_gcp_phase_batteries.py -v` | 0 | 89 tests, no skip line |
| `python3 scripts/gcp/test_redteam_packet.py -v` | 0 | 11 tests, no skip line |
| `python3 scripts/gcp/test_redteam_brain.py -v` | 0 | 7 tests, no skip line |
| `python3 tests/planning/test_r15_lifecycle.py -v` | 0 | 2 tests, no skip line |
| `python3 scripts/ci/test_optics_observe_ci.py -v` | 0 | 5 tests, no skip line |
| `python3 -m unittest deploy/docker/test_observe_example.py -v` | 0 | 3 tests, no skip line |

An exit of 0 does not prove a skipped case. The skipped rows above were not run.

## What those commands show

On `code_commit`, the license loader returns one usable key for a live build and none for a test build. A token signed with a throwaway test key is refused (`UNKNOWN_KID` against the live set, `TRUST_NOT_CONFIGURED` when the test-build key set is empty). A token for `lic-live-2026-10` signed by a throwaway key generated in the test is refused (`BAD_SIGNATURE`). Malformed license documents return an empty key set. The production artifact verifier refuses a bad signature from a throwaway key (`SIGNATURE_INVALID`). A one-byte change in a copy of the artifact trust entry does not match the published raw-key fingerprint, and verification with the unmutated public key returns `UNTRUSTED_KEY`.

These are fixture results on that commit. They do not prove a live host, a new boot, or that an instance was created or removed.

## Gap list

- Live fingerprint confirmation by the key owner.
- Production secret store configuration. This repository does not configure it, and the private keys were not read.
- App-side `VANTIO_LICENSE_PUBLIC_KEYS`. This change does not set that variable.
- A license token or artifact signature produced by the production private key. The tests used throwaway keys generated in the test process. No production signature was created.
