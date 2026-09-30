# Independent council

Audience: PUBLIC_PLANNING_PLACEHOLDER

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_REVISION_READY_FOR_COUNCIL`

This file is a public planning placeholder. The store producer does not sit the council and does not write a verdict. Producer agent identifiers, model names, and agent URLs are omitted from the public tip.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Packet | `docs/planning/optics-o7-store/` |
| Package | `@vantio/optics-operational-store` `0.0.0-unstable-pre-1.0` |
| Tests | `tests/optics-o7-store/` |
| Engine | Embedded SQLite, WAL, application-owned schema |
| Python mechanism | Standard-library `sqlite3` |
| Node binding | `UNSELECTED` |
| Classification the producer claims | `OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_REVISION_READY_FOR_COUNCIL` |
| Evidence tier | `UNSET` |
| Default write path | Off |
| `PACKAGES.json` `O7` cell | Left `NOT_AUTHORIZED` |
| Gate 8 | Left closed |

## 2. Seats (pending)

Six seats remain `UNSAT` until an independent council records a verdict. Private seat narrative is not published on this tip.

## 3. Checks the council can re-run

```sh
python3 tests/optics-o7-store/direct_test.py
python3 tests/optics-o7-store/adversarial_test.py
node --test tests/optics-o7-store/*.test.cjs
node --test tests/optics-option-c-revalidation/*.test.cjs
```

Also confirm: Node sources under `packages/optics-operational-store/` do not require `sqlite3` / `better-sqlite3` / `node:sqlite`; `@vantio/cli` remains `0.3.24`; Gate 8 stays closed; no tracked `*.sqlite` files.
