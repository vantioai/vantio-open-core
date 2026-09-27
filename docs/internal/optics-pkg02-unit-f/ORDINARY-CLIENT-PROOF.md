# PKG-02 Unit F ordinary-client proof

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

The proof opens four inputs. It does not rewrite them. Origins are the labels the contract already computes.

| Input | How it is opened | Origin | Optics display |
| --- | --- | --- | --- |
| CLI `0.3.24` `vantio run` of `node -e process.exit(0)` | `readRunFile` on the temporary run file | `LEGACY_UNMARKED` | `NOT_OBSERVED`. Not `SUCCESS`. Not `LOCAL_OBSERVATION`. |
| Python `3.1.0` `shield()` around one local `urlopen` | `readRunFile` on the temporary run file | `LEGACY_UNMARKED` | Stored `opticsStatus` `SUCCESS` displays as `UNAVAILABLE` with `optimistic_default_forbidden`. The file still contains `SUCCESS`. |
| CLI `0.3.24` `vantio demo` | `readRunFile` on the temporary demo file | Envelope `LEGACY_UNMARKED`. Observation `SIMULATED_DEMO`. | Optics `UNAVAILABLE`. Workload `application_status` `SUCCESS` stays on that dimension. Legacy `bytes` `0` displays as `response_bytes` `null`. |
| Unit A fixture `explicit-observed-not-default` | `explainFixture`, and `readRunFile` on a temporary file of that declared call | Not `LOCAL_OBSERVATION` | Explicit `OBSERVED`. Not optics `SUCCESS`. Workload `SUCCESS` stays separate. |

Unknown token `SUPER_SUCCESS` is covered by the direct and adversarial tests. It displays as `UNAVAILABLE` and the raw token is absent from the explanation.

Each file read compares the bytes before and after. `input_bytes_identical` is true. The reader does not write the path.
