# Operator runbook outline

Audience: INTERNAL_RESTRICTED

This is the operator outline for the script in `03-DEMO-SCRIPT.md`. It is not an installed tool.

## Before the room

1. Use a checkout that contains this demo directory and still has `@vantio/cli` version `0.3.24`. The design was written against base commit `1df51d29a65a3913f1ef1f29fc00ead1335ef7a0`.
2. Confirm `packages/vantio-cli/package.json` version is `0.3.24`.
3. Do not `npm install -g` a different CLI for the script. Invoke `node packages/vantio-cli/bin/vantio.js`.
4. Create an empty directory for the demo home. Record its absolute path. It must not be the operator's real home and must not be a directory that already contains `.vantio`.
5. Export `HOME` to that path for the shell that runs the commands.
6. Export `VANTIO_TELEMETRY_DISABLED=1`.
7. Leave `VANTIO_TELEMETRY` unset.
8. Leave `VANTIO_API_KEY` unset.
9. Working directory is the repository root.
10. Put the simulation banner where the room can read it before B07. Keep it through B10 and through B15, including `discover` and the F1 stop.
11. Have these files open: `03-DEMO-SCRIPT.md`, `08-CLAIM-LEDGER.json`, `09-LIMITATION-LEDGER.json`, `docs/PRODUCT_LINEUP.md`.

## During the room

1. Run beats B01 through B18 in order.
2. Run `demo` once. Save the printed trace id.
3. Run `prove` only with `--run` set to that trace id and `--format=md`.
4. If a command prints a block token, a redact token, or a dry-run block token, stop. That output is outside this script.
5. If the version line is not `0.3.24`, stop.
6. If `status` prints `opt-in` for telemetry, stop and fix the environment. The scripted word is `disabled`.
7. If the run file written by `demo` has a hostname other than `optics-demo.invalid`, stop. Do not explain that file as the stub. The F1 planted file is a different file and follows the stop rule in `01-SIMULATION-LABEL-RULE.md`.
8. At B15, run `discover` once while the banner is up and before F1 is planted. Then plant F1. On F1, an unlabeled synthetic file is discarded. The operator does not prove it, does not add it to a total, and does not resume a success narration. The operator still speaks B16–B18 as the close, including `L-FOUNDER-BEATS-ABSENT`. The operator does not keep speaking as if the demo succeeded with the unlabeled file.
9. Do not answer an improvised question by starting `vantio run` against a network.
10. Do not open a Phantom Engine repository and do not paste kernel output into the room.

## After a deviation

Scripted F1 is not a deviation. It follows the stop rule and still speaks B16–B18. A deviation is an unexpected file, token, version, or telemetry state.

1. Say that the script has stopped.
2. Do not continue with prove or discover on an unexpected file.
3. Reset with `05-RESET-OUTLINE.md` before any retry.
4. Record the deviation in the operator note for the council. Do not edit the claim ledger during the room to make the deviation pass.

## After the room

1. Reset.
2. Confirm the real home still has its own `.vantio` untouched, or confirm the operator had no `.vantio` and still has none.
3. Confirm the working directory has no `vantio-proof-*.html`.
4. Leave this directory's documents unchanged.
