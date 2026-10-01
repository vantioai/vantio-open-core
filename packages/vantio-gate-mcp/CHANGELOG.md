# @vantio/gate-mcp changelog

## 0.1.1

CANDIDATE_ONLY_NOT_FOR_PUBLICATION. This heading is source. It is not an npm release.

- `gate_get_policy` and `gate_residual_risk` no longer take an `api_key` tool argument. The key is `VANTIO_API_KEY` from the environment.
- Those tools no longer take an `api_base` tool argument. The control-plane host is `VANTIO_API_BASE` from the environment, or `https://api.vantio.ai` when that variable is unset or blank. A caller-supplied host is ignored, so the tool cannot send `VANTIO_API_KEY` to a URL the caller chooses.
