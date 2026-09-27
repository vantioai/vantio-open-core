# Optics PKG-02 — compatibility matrix

Audience: INTERNAL_RESTRICTED

The 104 cells are `RECORD-COMPATIBILITY-MATRIX.json`. Every cell has `achievement` `NOT_SHIPPED`. `FULL` means the planned reading of two conformant future records. It does not mean a release exists.

Abbreviations in the grid: `ADAPTER` is `REQUIRES_ADAPTER`, `UNSUP` is `UNSUPPORTED`, `REJECT` is `REJECT_WITH_EXPLANATION`, `ALIAS` is `REQUIRES_ALIAS`, `RO` is `READ_ONLY`, `NYD` is `NOT_YET_DECIDED`.

| Writer | CLI 0.3.24 | Future CLI | Future Node | Future Python | Python 3.1.0 | Mixed | Unknown enum | Missing canonical | Alias | Imported | Legacy unmarked | Proof | Future store |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CLI 0.3.24 | PARTIAL | ADAPTER | ADAPTER | ADAPTER | UNSUP | PARTIAL | REJECT | PARTIAL | ALIAS | RO | RO | PARTIAL | NYD |
| Future CLI | UNSUP | FULL | FULL | FULL | UNSUP | PARTIAL | REJECT | PARTIAL | ALIAS | RO | RO | ADAPTER | NYD |
| Node SDK 0.2.4 | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP | REJECT | PARTIAL | ALIAS | RO | RO | UNSUP | NYD |
| Future Node SDK | NYD | NYD | NYD | NYD | NYD | NYD | REJECT | PARTIAL | ALIAS | RO | RO | NYD | NYD |
| Python 3.1.0 | PARTIAL | ADAPTER | ADAPTER | ADAPTER | UNSUP | PARTIAL | REJECT | PARTIAL | ALIAS | RO | RO | PARTIAL | NYD |
| Future Python | UNSUP | FULL | FULL | FULL | UNSUP | PARTIAL | REJECT | PARTIAL | ALIAS | RO | RO | ADAPTER | NYD |
| Demo command | PARTIAL | ADAPTER | ADAPTER | ADAPTER | UNSUP | PARTIAL | REJECT | PARTIAL | ALIAS | RO | RO | PARTIAL | NYD |
| PKG-01 output | UNSUP | FULL | FULL | FULL | UNSUP | PARTIAL | REJECT | PARTIAL | ALIAS | RO | RO | ADAPTER | NYD |

Cell counts: `PARTIAL` 20, `READ_ONLY` 16, `UNSUPPORTED` 16, `NOT_YET_DECIDED` 15, `REQUIRES_ADAPTER` 12, `FULL` 9, `REJECT_WITH_EXPLANATION` 8, `REQUIRES_ALIAS` 8.

## Hard rules

- An old reader must not treat an unknown status as success. CLI 0.3.24 `displayCall` assigns `opticsStatus` `SUCCESS` to every call row. That is why future contract output is `UNSUPPORTED` on the frozen CLI reader. Shipping a future record and telling customers the frozen CLI understands it would break this rule.
- A future record must not silently overwrite an older file. Adapters are read-only. The source file stays the source file.
- An adapter preserves origin. It does not upgrade `LEGACY_UNMARKED` or `IMPORTED` to `LOCAL_OBSERVATION`.
- An unsupported record stays visible. `UNSUPPORTED` is a matrix result the operator can see. It is not a deleted file and not `NOT_OBSERVED`.
- PKG-02 performs no automatic conversion and no migration. `future_store_import` is `NOT_YET_DECIDED` because Founder decision 9 has not selected a binding, and because this packet forbids the import anyway.

## How to read the other columns

`PARTIAL` on CLI 0.3.24 reading itself, Python 3.1.0, or the demo means the frozen reader can open a `vantio_run_log` `"1"` file and will recompute status. It will also add `bytes || 0` into totals. That is a partial read, not a contract read.

`REQUIRES_ADAPTER` on a future reader of a live file means `legacyEnvelopeToContract` and `legacyCallToContract` in the private package are the interpretation. They are not wired into the live CLI or the live Python SDK. Turning them on is a later unit, still read-only.

`REQUIRES_ALIAS` means camelCase and legacy keys remain readable. The stored future key is the canonical name.

`READ_ONLY` on import and on `LEGACY_UNMARKED` means the label is preserved. Founder decision 6 is still unresolved, so no customer promote is in this matrix.

`REJECT_WITH_EXPLANATION` on unknown fields and enums means the contract reason is shown. Unknown `optics_status` becomes `UNAVAILABLE` with `OPTIMISTIC_DEFAULT_FORBIDDEN`. The explanation is the reason code, not a success token.

Python 3.1.0 as a reader is `UNSUPPORTED` because that package writes logs and does not read them. This plan does not add a reader to 3.1.0.

Node SDK 0.2.4 is `UNSUPPORTED` as a local record writer and reader. The future Node SDK cell is `NOT_YET_DECIDED` except where a hard rule already fixes the reader behavior.

Mixed versions stay `PARTIAL`: files from more than one writer sit side by side. None of them is rewritten to look like another.

Proof export of a live file is `PARTIAL` because prove JSON uses `publicCall` and MCP markdown uses `action` and `machine`. Proof export of a future record is `REQUIRES_ADAPTER`. This packet does not build that exporter.

Demo files need the adapter too. The observation host `optics-demo.invalid` is `SIMULATED_DEMO`. The adapter must not relabel that observation as `LOCAL_OBSERVATION`.
