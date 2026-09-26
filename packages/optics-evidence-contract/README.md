# Optics evidence contract

Audience: INTERNAL_RESTRICTED

Private package for PKG-01 Slice 1. `schema_status` is `unstable-pre-1.0`. This is not a stable schema, not a public API, and not a published package.

Option B: `@vantio/cli@0.3.24` and `vantio-agent-sdk` 3.1.0 do not import this package. Nothing here writes a run file or a database.

Validators:

- `src/validate.cjs`
- `src/validate.py`

Both read `contract/`. Tests and the shared corpus live in `tests/optics-evidence-contract/`. Internal notes live in `docs/internal/optics-pkg01/`.

The contract output is a result object. It does not change a caller-supplied application result.
