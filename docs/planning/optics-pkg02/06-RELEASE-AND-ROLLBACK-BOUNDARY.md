# Optics PKG-02 — release units and rollback

Audience: INTERNAL_RESTRICTED

No unit in this list is authorized. No unit includes `@vantio/cli` `0.3.24`. No unit publishes, seals, or opens a release candidate. Frozen CLI source stays out of every unit.

## 1. Units

### Unit A — shared vocabulary and compatibility fixtures

| Item | Boundary |
| --- | --- |
| Source scope | Future fixture files that import the private contract only. Not live CLI, Python, or Node SDK trees. |
| Runtime effect | None. Tests do not write `~/.vantio/runs` and do not open a network. |
| Record-format effect | None on customer files. |
| Rollback | Delete the fixture commit. No customer file changes. |
| Compatibility | Fixtures cover both live shapes and the canonical shape. |
| Privacy risk | Fixtures use the existing corpus rules. No new secret material. |
| Release gate | Independent council of that future force. Not this packet. |
| Ordinary-client proof | Not required. No client writes a record. |
| Merge eligibility | Separate from B–F. |
| Depends on | This planning packet accepted by council. Does not depend on a version bump. |

### Unit B — Node adapter, inert

| Item | Boundary |
| --- | --- |
| Source scope | A future module that calls the existing mapper on copies. Not `packages/vantio-cli/bin/` of 0.3.24. |
| Runtime effect | None on `vantio run`. The adapter is not on the exit path. |
| Record-format effect | None. Output is detached and discarded by the test. |
| Rollback | Remove the module. Live files stay as 0.3.24 writes them. |
| Compatibility | Read-only. Origin is not upgraded. `bytes` `0` becomes null only in the detached copy. |
| Privacy risk | The mapper already strips prohibited names. The adapter must not log the rejected value. |
| Release gate | Council plus the shared fixtures from Unit A green on Node. |
| Ordinary-client proof | Show a real 0.3.24 run file is byte-identical before and after the adapter package is present. |
| Merge eligibility | May merge without Unit C and without activation. |
| Depends on | Unit A. |

### Unit C — Python adapter, inert

| Item | Boundary |
| --- | --- |
| Source scope | A future module beside the contract, or a future Python tree that is not the 3.1.0 line. `packages/vantio-agent-sdk-py/vantio/` of 3.1.0 is out of scope. |
| Runtime effect | None on `shield()`. |
| Record-format effect | None. |
| Rollback | Remove the module. 3.1.0 files stay as 3.1.0 writes them. |
| Compatibility | Same read-only rules as Unit B. Python `+00:00` timestamps normalize only in the copy. |
| Privacy risk | Same strip rules. Comma-joined `mediation` becomes `unknown` or is split only in the copy, and the split must not invent events. |
| Release gate | Council plus Unit A fixtures green on the claimed CPython versions. |
| Ordinary-client proof | A 3.1.0 run file is byte-identical before and after. |
| Merge eligibility | Independent of Unit B and of activation. |
| Depends on | Unit A. |

### Unit D — Node writer activation

| Item | Boundary |
| --- | --- |
| Source scope | `PKG02-FUTURE-CLI-UNASSIGNED` only. |
| Runtime effect | New runs from that CLI version write canonical records. Old binaries keep writing the 0.3.24 shape. |
| Record-format effect | New files only. |
| Rollback | Ship the previous writer behavior for new runs. Leave already-written canonical files in place and mark them readable only with disclosure. Do not convert them back in a way that looks like `SUCCESS`. |
| Compatibility | CLI 0.3.24 is `UNSUPPORTED` as a reader of the new file. The release notes have to say that. |
| Privacy risk | Activation must not start storing prompts, hostnames of the machine, or cost. |
| Release gate | Council, Unit B, Unit F, and an ordinary-client proof on a machine that still has CLI 0.3.24 installed beside the new CLI. |
| Ordinary-client proof | One in-scope call, one empty wrap, one missing content-length, one HTTP 500, one network error. Files show `OBSERVED` or `UNAVAILABLE`, never a filled `SUCCESS` for a missing optics token, and never `response_bytes` `0` for a missing length. |
| Merge eligibility | Its own release. Not combined with Unit E. |
| Depends on | A, B, F. |

### Unit E — Python writer activation

| Item | Boundary |
| --- | --- |
| Source scope | `PKG02-FUTURE-PYTHON-UNASSIGNED` only. Not 3.1.0 and not 3.0.15. |
| Runtime effect | New `shield()` writes canonical records. 3.1.0 keeps its current writer. |
| Record-format effect | New files only. Empty wraps stay an explicit `NOT_OBSERVED` envelope or stay absent, and the release says which. They do not become a file with `optics_status` `SUCCESS`. |
| Rollback | Same as Unit D, for the Python version only. |
| Compatibility | 3.1.0 has no reader. The future CLI reader from Unit F is the cross-language check. |
| Privacy risk | Same prohibitions. Customer exception text stays an `error_class` token, not a message. |
| Release gate | Council, Unit C, Unit F, ordinary-client proof. |
| Ordinary-client proof | urllib, one async client, one socket failure, one HTTP 4xx, one empty `shield()`, one subprocess size. |
| Merge eligibility | Its own release. Not combined with Unit D. |
| Depends on | A, C, F. |

### Unit F — reader compatibility release

| Item | Boundary |
| --- | --- |
| Source scope | A future reader. Not the frozen CLI binary. |
| Runtime effect | Read and explain. No write back. |
| Record-format effect | None. |
| Rollback | Remove the reader. Old files remain. New files, if any already exist, stay on disk and the rollback notice says they are not readable by the rolled-back binary. |
| Compatibility | Legacy, demo, import, and canonical inputs. Unknown status stays `UNAVAILABLE`. |
| Privacy risk | Reader output must not echo stripped secrets. |
| Release gate | Council and fixture proof that unknown optics tokens do not display as success. |
| Ordinary-client proof | Open one 0.3.24 file, one 3.1.0 file, one demo file, and one canonical fixture. Origins on the first three stay `LEGACY_UNMARKED` or `SIMULATED_DEMO` as the contract already computes. |
| Merge eligibility | Can ship before D and E. Cannot ship inside the 0.3.24 package. |
| Depends on | Unit A. Benefits from B and C and does not require them to be activated. |

## 2. Rollback model

Rollback applies to a future integration. This planning commit has nothing to roll back except itself, and deleting it changes no product behavior.

A future rollback must not:

- Persist a prohibited field in order to "restore" a legacy file. The original file is still there. The rollback does not rewrite it.
- Map an unknown or canonical status back to `SUCCESS`.
- Make a new file unreadable without saying so. The disclosure is `UNSUPPORTED` plus the `schema_status` the file carries.
- Drop `evidence_origin` or replace it with `LOCAL_OBSERVATION`.
- Upgrade `IMPORTED` or `LEGACY_UNMARKED`.
- Report a partial rollback as a complete run. `lifecycle` and completeness tokens stay.

Rollback of an inert adapter is removal of unused code. Customer records do not change.

Rollback of an activated writer stops the new writer for subsequent runs. Files already written in the new shape remain. They are not deleted, because deletion would look like `NOT_OBSERVED`. They are not converted in place. A reader that cannot understand them shows `UNSUPPORTED` and the schema marker.

Fail-open stays a property of the workload call. A validator failure does not become a successful observation, and it does not change the caller return value. That rule is already how the private contract returns `application_result`. Activation must keep it.

No rollback path in this design runs a migration, chooses a SQLite binding, or rewrites history.
