# Architecture notes for council

Audience: INTERNAL_RESTRICTED

These are the producer's decisions. They are not a council verdict.

## 1. CLI 0.3.24 stays frozen

The labeled writer lives in `@vantio/investor-demo-wave2`. The frozen `demo` command is invoked as a subprocess when it is present and prints `0.3.24`. The runner does not patch its files. The CLI run file still has no `evidence_origin`. The wave2 envelope, stored at `.vantio/demo-session/labeled-envelope.json`, carries `evidence_origin` `SIMULATED_DEMO` and `producer` `demo_command`. That file has no `vantio_run_log` marker, so the frozen CLI does not treat it as a run.

`producer_version` is `wave2-0.0.0`. It matches the architecture charset `[A-Za-z0-9._+-]` and the 32-character limit. The demo producer does not accept `LOCAL_OBSERVATION`.

A fixed envelope trace id is `--trace-id` with the form `0x` plus 16 hex characters. A fixed timestamp is `--started-at` in UTC millisecond form. Those flags do not change the CLI file's trace id.

## 2. Proof class on every card

| Class | Meaning in this runner |
| --- | --- |
| `INTERNAL_FUNCTIONAL` | The check ran in this session and the result is in the export. |
| `SIMULATED_LABELED` | The row is a labeled simulation and was not applied as a product event. |
| `NARRATED_BOUNDARY` | The room states a document boundary. No event file was created for it. |
| `OFFLINE_FALLBACK` | The frozen CLI was not used. The committed fallback is labeled. |
| `HELD_NOT_EXECUTED` | The step has not run. Uninstall uses this until the demo home is removed. |

`PROVED_EXTERNAL` and `CUSTOMER_VALIDATED` are not members of the class list. Every card sets `external_proof` to `NOT_PROVED_EXTERNAL`.

## 3. Simulations

A card with `is_simulation` true must use `SIMULATED_DEMO`, `NARRATED_BOUNDARY`, or `INJECTED_UNLABELED_SYNTHETIC`. `LIVE_LOCAL_OBSERVATION` is refused. Customer activity total is fixed at 0. The CLI sentence `observed locally` is stored as not a customer total.

The banner is `SIMULATION — SIMULATED_DEMO — vantio demo — no network — not a customer call`.

## 4. Cards

| Card | What the session does | Proof class when the CLI ran |
| --- | --- | --- |
| Workload discovery | Scans the demo home. Simulated and unlabeled rows are excluded from the customer total. | `INTERNAL_FUNCTIONAL` |
| Optics observation | Runs `demo` once, or records the offline fallback. | `INTERNAL_FUNCTIONAL` |
| Coverage | Checks the supported-path rule that unobserved is not blocked. No agent is started. | `NARRATED_BOUNDARY` |
| Ingress and egress | Records one labeled egress stub. Opens no listener. Ingress is `NOT_OBSERVED`. | `SIMULATED_LABELED` |
| Policy proposal | Records a proposal and does not apply it. | `SIMULATED_LABELED` |
| Simulation | Writes the banner and the labeled envelope. | `INTERNAL_FUNCTIONAL` |
| Canary enforcement | Drops a privacy canary before storage. Writes no enforcement action. | `INTERNAL_FUNCTIONAL` |
| Allowed and blocked | Stores permit and deny shapes with `applied` false. Run files must not contain enforcement tokens. | `SIMULATED_LABELED` |
| Descendant authority | A fixture subset stays `PROPOSED`. A widening or redelegating child is `REFUSED`. `ACTIVE` is not set. | `INTERNAL_FUNCTIONAL` |
| Health degradation | Accepts `degraded` only when the WS4 catalog lists it. No host is enrolled. | `SIMULATED_LABELED` |
| Recovery | Session record returns to `observing`. Host state stays `not_enrolled`. | `INTERNAL_FUNCTIONAL` |
| Evidence export | Writes the labeled JSON export. It is not an HTML customer report. | `INTERNAL_FUNCTIONAL` |
| Revocation | Revokes the demo sentinel. Does not rotate a credential or a customer grant. | `INTERNAL_FUNCTIONAL` |
| Rollback | Returns policy to `ROLLED_BACK` and health to `not_enrolled`. Does not delete run files. | `INTERNAL_FUNCTIONAL` |
| Uninstall | Removes the recorded demo home. Refuses the operator home, the checkout, and a symlink. | `INTERNAL_FUNCTIONAL` after removal |
| Independent verification | Recomputes the export hash and the invariants in a second function. Council stays pending. | `INTERNAL_FUNCTIONAL` |

When the CLI is missing, the version is not `0.3.24`, or `--offline` is set, discovery and observation use `OFFLINE_FALLBACK`. A CLI that runs and then fails the stub checks is `LIVE_DEVIATION`, and the export is `INVESTOR_DEMO_WAVE2_BLOCKED`. The fallback is not used to hide that deviation.

## 5. F1

On request, the runner plants `0xinjectunlabeled01` after `discover`. The file has no `evidence_origin` and its host is not `optics-demo.invalid`. Disposition is `DISCARDED`. The runner does not prove it, does not add it to the customer total, and does not set a success narration. B16–B18 remain in the beat list, including `L-FOUNDER-BEATS-ABSENT`. Uninstall deletes the file with the demo home.

## 6. Reset

The sentinel records the demo home, the operator home, and the repository root. The demo home must be the `demo-home` child of a session directory under the OS temp directory. Uninstall deletes that directory and any new `vantio-proof-*.html` recorded for the session, except paths under the operator home. A second uninstall reports `already_removed` and does not delete the operator home.

## 7. Readiness

`visual_completion_counts` is false. The ready classification requires the invariant list to be empty and the uninstall card to be executed. The local verifier checks the canonical SHA-256. A mismatch or a classification that does not match the invariants fails the verifier.
