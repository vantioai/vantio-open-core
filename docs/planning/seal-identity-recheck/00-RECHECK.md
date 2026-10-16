# Seal identity re-check

UTC: 2026-10-16

Lane digest under re-check: `6d3ce580` (full value in `RESULT.json`).

Current main stores that digest as `COMPARISON_SEAL` in `scripts/gap/t1-stranger-host/constants.py`. `WORKING_SEAL` remains the `bbb1025d` constant. The installer public pin remains `e0b19d55` on `pe_archive_sha256`. This re-check does not move any of those constants.

## What was checked

`scripts/release/seal-identity-recheck.mjs` reads those constants, hashes every file in this tree except `.git`, `node_modules`, caches, and this directory, and does that hash pass twice.

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

A rebuild of the `6d3ce580` OCI archive needs the private engine sources and the build inputs named in `docs/planning/phantom-engine-production/02-P1-PACKAGE-ARTIFACT-PROVENANCE.md`. Those inputs are not in this repository. This re-check does not fetch them and does not start a lab.

## Labels

The tree facts above are **Verified** for this checkout. The engine archive itself is **Lab-only**. Nothing here is a claim that two clean engine builds match.
