# @vantio/gate-mcp changelog (documentation record)

This heading exists so a documentation release can require a changelog entry for the version already in `packages/vantio-gate-mcp/package.json`. It does not bump that version.

## 0.1.1

CANDIDATE_ONLY_NOT_FOR_PUBLICATION. Source version only. Not an npm release.

`gate_get_policy` and `gate_residual_risk` read `VANTIO_API_KEY` from the environment. They do not take an `api_key` tool argument. Host matching uses a DNS suffix. `dry_run: false` names `BLOCKED_*` actions. `dry_run: true` keeps the `DRY_RUN_` prefix. The tools still do not block network traffic.

## 0.1.0

Documentation baseline at `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`. `@vantio/gate-mcp` remains a legacy compatibility package. Gate is not a separate product. Product behavior is unchanged by this documentation record.
