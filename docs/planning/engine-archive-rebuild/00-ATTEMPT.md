# Engine archive rebuild attempt

UTC: 2026-10-16

This attempt rebuilds the Phantom Engine OCI archive from source and compares the file digest to `WORKING_SEAL` (`8b1106ef` since 2026-10-22, `6d3ce580` at the time of the 2026-10-16 attempt; full value in `RESULT.json`).

The comparison has three results:

| Result | Meaning |
| --- | --- |
| `MATCH` | A rebuilt archive was hashed and the digest equals `WORKING_SEAL` |
| `MISMATCH` | A rebuilt archive was hashed and the digest does not equal `WORKING_SEAL` |
| `NOT_PERFORMED` | No archive was produced, so there is no digest to compare. This is not a match and not a mismatch |

`formal_reproducibility` stays `NOT_CLAIMED`. The label on every result here is **Lab-only**.

## What this run did

`scripts/release/engine-archive-rebuild.mjs` asks `git ls-remote` for `vantioai/vantio-phantom-engine` and looks for a local tree that has `Cargo.toml` plus a Dockerfile that names `vantio-loader` or `bpf-linker`. Those are the inputs named in `docs/planning/phantom-engine-production/02-P1-PACKAGE-ARTIFACT-PROVENANCE.md`.

When a tree is found, the script runs `docker build` on that Dockerfile and `docker save` of the local tag, then hashes the tar. On this checkout the remote is not readable and no local engine tree was found, so that build did not start. `comparison` is `NOT_PERFORMED` and `reason` is `source_unavailable`. `match` is null. No rebuilt digest is recorded.

A later run that has the source can produce `MATCH` or `MISMATCH`. Until then this page does not claim the seal bytes were reproduced, and it does not claim they differ.

## 2026-10-22 lane seal move

`release/pe-canonical-seal.json` now points `lane_seal` at `8b1106ef`, so `working_seal` in `RESULT.json` follows it. Every other field in `RESULT.json` (`remote_ok`, `remote_exit_code`, `remote_stderr`, `source_dir_found`, `comparison`, `reason`) is still the 2026-10-16 attempt from a checkout that could not read the engine remote. This page did not rerun that attempt.

`8b1106ef` is a `docker save` of `vantio-phantom-engine:da961aa9`, built outside this repository from phantom-engine `da961aa92ab75f3566ec086dc612fdda80807191`. An earlier build from the same commit, tagged `:local`, hashed to `e9eeb058`. Two builds of one commit gave two different digests, because the Dockerfile installs a floating Rust nightly and an unpinned `bpf-linker`. That is a reason `formal_reproducibility` stays `NOT_CLAIMED`. It is not a `MISMATCH` result here, because this script did not build either archive.

