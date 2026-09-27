# @vantio/optics-operational-store

PRIVATE. `schema_status` is `unstable-pre-1.0`. Not published. Not a default write path.

The file engine is embedded SQLite with WAL. Python uses the standard-library `sqlite3` module. The selected Node binding is `node:sqlite@24.15.0`: Node.js 24 at or above 24.15.0, and Node.js 26. There is no npm dependency. `better-sqlite3` is not installed and is not loaded when `node:sqlite` cannot load.

Below that floor, including Node.js 22, `openStore` returns `NODE_BINDING_CANNOT_LOAD`, the application continues, and no store file is created.

Callers use put, get, and the query request. A caller-supplied SQL string is rejected. Backup is a filesystem copy.

Classification: `O7_RUNTIME_INTEGRATION_READY_FOR_COUNCIL`. Evidence tier `UNSET`. Gate 8 stays closed. This package does not claim a host proof.

Packet: `docs/internal/optics-o7/00-BINDING-DECISION.md`. Runtime record: `docs/internal/optics-o7/10-RUNTIME-INTEGRATION.md`.
