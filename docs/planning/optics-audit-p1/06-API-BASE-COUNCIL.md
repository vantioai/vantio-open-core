# Optics audit api_base independent council

Audience: review of source changes on this branch.

Status: `PASS_WITH_NONBLOCKING_NOTES`

`council_pass`: true

`council_verdict`: `PASS_WITH_NONBLOCKING_NOTES`

`merge_state`: `WAITING_FOR_AUTHORIZED_REVIEWER`

`split_done`: false

Publication: `CANDIDATE_ONLY_NOT_FOR_PUBLICATION`. No npm publish, no PyPI publish, no install.vantio.ai go-live.

This verdict reviews tip `1c15407f82f7d43548e9fb0b3a3cf037b0ba70b7`. It is not a GitHub approval and it is not kvantio. kvantio still has to APPROVE before anyone merges. The commit that records this file is documentation of that review.

## Packet

| Finding | Result | Tests |
| --- | --- | --- |
| `gate_get_policy` and `gate_residual_risk` took `api_base` and sent `VANTIO_API_KEY` to that host | Closed on the reviewed tip. Both tools register an empty input schema and call the fetch helpers with no arguments. `controlPlaneBase` reads `VANTIO_API_BASE` only. Unset or blank uses `https://api.vantio.ai`. A caller object or string is unused. | `packages/vantio-gate-mcp/test/api_base_host.test.js`, `packages/vantio-gate-mcp/test/api_key_env.test.js` |

Independent re-run of those two files: 10 pass, 0 fail.

`tool_argument_can_redirect_key`: false

## Residual

An operator-set `VANTIO_API_BASE` still chooses the host that receives `VANTIO_API_KEY`. That variable is environment config, not a tool argument.

The observe image pins `@vantio/cli@0.3.25` as a version string, not an image digest.

Opening the stage parent follows intermediate path components. The stage entry itself is opened with `lstat` and `O_NOFOLLOW`.

P1 and P2–P5 remain one pull request. Cherry-picking P2–P5 onto the pre-P1 base conflicts, and this branch was not rewritten. See `05-SPLIT-DECISION.md`.

## Verdict

| Field | Value |
| --- | --- |
| Council identity | independent read of tip `1c15407f82f7d43548e9fb0b3a3cf037b0ba70b7` |
| Reviewer | not kvantio |
| Date | 2026-09-30 |
| Result | `PASS_WITH_NONBLOCKING_NOTES` |
| Notes | The fetch tools do not take `api_base` or `api_key`. The registered handlers ignore a supplied `api_base`. The key stays on the environment host. Residuals above stay open. |
