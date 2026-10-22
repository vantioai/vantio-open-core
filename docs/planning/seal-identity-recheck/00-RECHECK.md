# Seal identity re-check

UTC: 2026-10-16

Refreshed: 2026-10-22, when the lane seal moved from `6d3ce580` to `8b1106ef`.

Lane digest under re-check: `8b1106ef` (full value in `RESULT.json`).

Current main stores that digest as `WORKING_SEAL`. `PREVIOUS_WORKING_SEAL` keeps the `bbb1025d` constant. `COMPARISON_SEAL` is an alias of `WORKING_SEAL`. The installer public pin remains `e0b19d55` on `pe_archive_sha256`. This re-check does not move any of those constants. `constants_moved: false` describes the script. The lane seal itself was moved by the 2026-10-22 edit of `release/pe-canonical-seal.json`, and `RESULT.json` was regenerated after that edit.

## What was checked

`scripts/release/seal-identity-recheck.mjs` reads the lane digest and the public pin from `release/pe-canonical-seal.json`. The previous working seal is in `release/pe-seal-history.json`. The stranger-host file still aliases `COMPARISON_SEAL` to `WORKING_SEAL`. The script hashes every file in this tree except `.git`, `node_modules`, and caches, and records any file whose digest is the working seal. A second hash pass covers six build-chain inputs: the stranger-host seal constants, the installer pin file, the Optics observe Dockerfile, the open-core provenance workflow, this script, and `release/pe-canonical-seal.json`.

| Fact | Result | Label |
| --- | --- | --- |
| The two hash passes of this tree agree | See `open_core_manifest_passes_agree` | Verified when they agree |
| A file in this tree has the lane digest | `bytes_matching_digest` is empty | Verified for this tree |
| `seal.oci.tar` is in this tree | absent | Verified for this tree |
| `Cargo.toml` is in this tree | absent | Verified for this tree |
| A Dockerfile here builds `vantio-loader` or `bpf-linker` | no | Verified for this tree |
| The private engine OCI bytes were built again and compared to the lane digest | not done | Lab-only |
| `formal_reproducibility` | `NOT_CLAIMED` | unchanged |

The open-core manifest hash is not the lane digest. Matching passes mean this script read the same bytes twice. They do not mean the engine image was rebuilt.

A rebuild of the lane OCI archive needs the private engine sources and the build inputs named in `docs/planning/phantom-engine-production/02-P1-PACKAGE-ARTIFACT-PROVENANCE.md`. Those inputs are not in this repository. This re-check does not fetch them and does not start a lab.

## Labels

The tree facts above are **Verified** for this checkout. The engine archive itself is **Lab-only**. Nothing here is a claim that two clean engine builds match.
