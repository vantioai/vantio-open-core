# @vantio/optics-operational-store

PRIVATE. `schema_status` is `unstable-pre-1.0`. Not published. Not a default write path.

The file engine is Python’s standard-library `sqlite3` module, with WAL and an application-owned schema. The Node binding is not selected. The Node entry returns `NODE_BINDING_UNSELECTED` and does not create a file.

Callers use put, get, and the query request. A caller-supplied SQL string is rejected.

Packet: `docs/planning/optics-o7-store/00-STORE.md`.

Classification: `OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_READY_FOR_COUNCIL`. Evidence tier `UNSET`.
