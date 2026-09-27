# PKG-02 Unit F compatibility

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

The reader accepts legacy, demo, import, and canonical inputs. It does not migrate them. Customer bytes stay the customer bytes.

| Input | Reading |
| --- | --- |
| CLI `0.3.24` run log | Legacy marker kept. `schema_version` `2` stays `compatibility.legacy_schema_version`. Canonical `schema_version` is `0`. Origin `LEGACY_UNMARKED`. |
| Python `3.1.0` run log | Same legacy rules. Stored `opticsStatus` `SUCCESS` displays as `UNAVAILABLE`. Comma-joined `mediation` is omitted rather than split into extra events. |
| Demo file | Observation host `optics-demo.invalid` is `SIMULATED_DEMO`. The envelope stays `LEGACY_UNMARKED`. It is not relabeled `LOCAL_OBSERVATION`. |
| Import | `IMPORTED` and `original_evidence_origin` stay. Maturity is not upgraded. |
| Canonical fixture | Explicit `OBSERVED` stays. A frozen CLI reader of that shape remains `UNSUPPORTED` because `displayCall` still returns `SUCCESS`. This package is not that frozen reader. |
| Unknown optics token | `UNAVAILABLE` with `OPTIMISTIC_DEFAULT_FORBIDDEN`. The explanation is the reason, not a success token. |
| Node SDK `0.2.4` ingest | `UNSUPPORTED`. No local record is invented. |

Every matrix cell in `RECORD-COMPATIBILITY-MATRIX.json` stays `achievement` `NOT_SHIPPED`. This unit does not edit that file.

The reader may ship before Units D and E. It must not ship inside the `0.3.24` package. Rollback of this unit is removal of the unused reader. Old files remain.
