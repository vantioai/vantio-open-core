# Independent council — O7 Node SQLite binding

Audience: INTERNAL_RESTRICTED

Council: `bc-00af4334-6f4f-59be-9ebf-c084d3c9baa6`, model Grok 4.7.

Council URL: https://cursor.com/agents/bc-00af4334-6f4f-59be-9ebf-c084d3c9baa6

Repository: `vantioai/vantio-open-core`

Starting commit: `0620f10ee52d3abcea18c1c988df02f687f51b36`

Observed: 2026-09-27

## Verdict

`O7_NODE_BINDING_COUNCIL_PASSED`

Selected binding: `node:sqlite@24.15.0`

The module is Node's built-in `node:sqlite`. `24.15.0` is the minimum Node.js version. Node.js 24.x from 24.15.0 onward, and Node.js 26.x, are the supported lines. There is no npm package to pin.

Fallback, not installed and not loaded on failure: `better-sqlite3@13.0.3`.

Engine: embedded SQLite with WAL. Unchanged.

## What the pass covers

The pass closes the selection Founder decision 9 left open. Track 2 may implement this binding and no other, inside the limits in `docs/internal/optics-o7/00-BINDING-DECISION.md`.

The pass does not open a database, change `openStore`, open Gate 8, or assign an evidence tier. Evidence tier stays `UNSET`. A reader who runs the store on this commit still receives `NODE_BINDING_UNSELECTED`.

`docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` still contains the sentence "9. Node SQLite binding. Not selected." This council left that sentence in place because the existing store tests lock it. The selection lives in this file and in the internal packet. Track 2 follows this verdict when the two disagree about which library to use. Track 2 follows the running code when asked what the process does today.

## Why this binding

The store file is created by Python's standard-library `sqlite3` with WAL, `BEGIN IMMEDIATE`, `user_version`, and prepared statements. The Node side has to open that same host file. `node:sqlite` does that inside the Node binary the operator already runs, with a documented busy-timeout default of 0, which matches the Python store's `timeout=0`.

`better-sqlite3@13.0.3` can also open a host SQLite file, and its own API is semver-stable on Node.js `>=22`. It is a native addon, its default busy timeout is 5000 ms, and it vendors SQLite 3.53.4. That package stays the named fallback for a later council that must cover Node.js 22 or that refuses a release-candidate module. This council does not install it.

`node:sqlite` is a release candidate, Stability 1.2, on the Node.js v26.8.1 documentation. It is not Stability 2. The Node.js 22 documentation still calls it experimental. This environment is Node.js v22.14.0 and printed `ExperimentalWarning: SQLite is an experimental feature and might change at any time`. The floor is 24.15.0 because that is the 24.x revision whose documentation first marks the module as a release candidate, and because 24.0.0 is where the `timeout` option exists on that line. Node.js 22 stays unsupported for this selection.

Full candidate table, probe log, platform list, and Track 2 limits: `docs/internal/optics-o7/00-BINDING-DECISION.md`.

## Seats

| Seat | Question | Result |
| --- | --- | --- |
| 1 | Engine remains embedded SQLite with WAL | Pass. No other engine selected. |
| 2 | Same host file as Python `sqlite3`, including WAL sidecars | Pass for the selected class of binding. A workstation probe on Node.js 22.14.0 shared one temp file with Python SQLite 3.45.1. That Node is below the floor. |
| 3 | Transactions, rollback, prepared statements | Pass on the probed build for `BEGIN IMMEDIATE`, `ROLLBACK`, `COMMIT`, and `StatementSync`. Floor 24.15.0 was not executed here. |
| 4 | Ordinary install and supply chain | Pass. No npm dependency. Fail-open when the module is absent. |
| 5 | Long-term support | Recorded gap. Release candidate, not Stability 2. Supported lines are Node.js 24 `>=24.15.0` and Node.js 26. |
| 6 | Frozen CLI and Python SDK | Pass. Versions `0.3.24` and `3.1.0` are unmodified. |
| 7 | Runtime proof | Not claimed. Evidence tier `UNSET`. Gate 8 closed. |

## Reading rule

On a conflict about the library name, `docs/internal/optics-o7/BINDING-DECISION.json` is the selection. On a conflict about current process behavior, the running `openStore` result wins until Track 2 changes it.
