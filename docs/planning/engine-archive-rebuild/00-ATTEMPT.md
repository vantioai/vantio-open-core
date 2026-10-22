# Engine archive rebuild attempt

UTC: 2026-10-16

This attempt rebuilds the Phantom Engine OCI archive from source and compares the file digest to `WORKING_SEAL` (`e9eeb058`, full value in `RESULT.json`).

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
