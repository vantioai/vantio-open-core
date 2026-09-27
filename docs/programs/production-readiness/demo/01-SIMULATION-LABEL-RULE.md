# Simulation-label rule

Audience: INTERNAL_RESTRICTED

Status: design rule for the investor demo. CLI 0.3.24 does not enforce this rule. Wave 2 is not authorized to change the CLI from this force.

## Rule

Every synthetic event in the investor room carries a simulation label before anyone in the room treats it as something that happened.

An unlabeled synthetic event stops the demo. The operator does not prove it, does not add it to a customer total, and does not keep speaking.

Stored action `OBSERVED` is the free Optics action token. It is not a simulation label.

## Labels

| Label | Use in this demo | Counted as customer activity |
| --- | --- | --- |
| `SIMULATED_DEMO` | `vantio demo` and any design envelope that stands in for that stub | No |
| `NARRATED_BOUNDARY` | Spoken product boundary with no event file | No |
| `INJECTED_UNLABELED_SYNTHETIC` | The failure-injection wrapper only. The inner defect is not shown as an event | No |
| `LIVE_LOCAL_OBSERVATION` | Reserved. This script does not produce one | Would require a real wrapped process and a separate label check |

`TEST_FIXTURE` is an architecture writer origin. This demo does not write test fixtures into a run directory.

`LOCAL_OBSERVATION` is an architecture writer origin for a real local capture. This demo does not stamp it. The current demo writer does not stamp any origin.

## What the room must see

Before `vantio demo`, the operator says and leaves visible:

`SIMULATION — SIMULATED_DEMO — vantio demo — no network — not a customer call`

The same banner stays up for `vantio prove` and `vantio discover` on that file.

The banner is the label for CLI 0.3.24, because the run file has no `evidence_origin` field. Hostname `optics-demo.invalid` is the additional visible marker inside the file. The architecture reader rule in `docs/architecture/optics-foundation/02-EVIDENCE-AND-PRIVACY-CONTRACT.md` maps that hostname to `SIMULATED_DEMO` on read. The shipped CLI reader does not apply that rule. The operator applies it in the room.

## File rule

A file dropped into a demo home is synthetic when a person or `vantio demo` created it for the room.

- If the file has `evidence_origin` `SIMULATED_DEMO` and `producer` `demo_command`, the label is on the file. The spoken banner is still required.
- If the file has hostname `optics-demo.invalid` and no origin field, the spoken banner is required and the missing field is limitation `L-DEMO-FILE-UNLABELED`.
- If the file has neither an origin field nor hostname `optics-demo.invalid`, it is an unlabeled synthetic event when the operator planted it. Stop. Disposition: discard. Do not run `vantio prove` on it.

Narrated boundaries do not get a run file. Phantom Engine enforce, host enrollment, and cluster behavior are narration. They are not events in `~/.vantio/runs/`.

## Proof artifacts

`vantio prove` on a demo file renders host, bytes, status, and trace id. The HTML and Markdown it writes do not contain `SIMULATED_DEMO`. Handing that artifact to an investor without the banner violates this rule. The scripted prove path is `--format=md` or `--json` while the banner is on screen. The operator does not leave a proof file behind as if it were a customer report.

## Design envelope

`scaffolding/labeled-event-envelope.json` is a labeled design object. It is not a run log. It has no `vantio_run_log` marker. It must not be copied into a runs directory.

## Wave 2 requirement, not authorized here

A later implementation force, after its own authorization, makes the demo writer persist `evidence_origin` `SIMULATED_DEMO` and `producer` `demo_command`, and makes readers exclude that origin from customer totals. This document does not open that work.
