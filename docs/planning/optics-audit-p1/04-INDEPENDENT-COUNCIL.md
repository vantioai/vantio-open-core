# Optics audit P1 independent council

The `api_base` residual named in this file is closed on tip `1c15407f82f7d43548e9fb0b3a3cf037b0ba70b7`. That later review is `06-API-BASE-COUNCIL.md`. The verdict below still reviews tip `1bbed9021c9ceb494b34d1d3ab4d625d5e7c32f3`.

Audience: review of source changes on this branch.

Status: `PASS_WITH_NONBLOCKING_NOTES`

`council_pass`: true

`council_verdict`: `PASS_WITH_NONBLOCKING_NOTES`

`merge_state`: `WAITING_FOR_AUTHORIZED_REVIEWER`

Publication: `CANDIDATE_ONLY_NOT_FOR_PUBLICATION`. No npm publish, no PyPI publish, no install.vantio.ai go-live.

This verdict reviews tip `1bbed9021c9ceb494b34d1d3ab4d625d5e7c32f3`. It is not a GitHub approval and it is not kvantio. kvantio still has to APPROVE before anyone merges.

## Packet

| Finding | Result | Tests |
| --- | --- | --- |
| Installer `remove_stage` followed a stage symlink that stayed inside the parent, then `shutil.rmtree` raised instead of refusing | Reproduced. Removal now `lstat`s the stage, opens it with `O_NOFOLLOW`, and refuses a symlink. Child symlinks are unlinked. Their targets stay. | `tests.test_live_executor.LiveExecutorTests.test_remove_stage_refuses_symlink_and_does_not_follow_it`, `test_remove_stage_does_not_follow_a_symlink_inside_the_directory`, `test_fixture_remove_stage_refuses_symlink` |
| `_privilege_ok` treated `sudo` on `PATH`, and a docker-group socket writer, as a live grant | Reproduced. Live apply, rollback, and uninstall require effective uid 0. | `test_sudo_on_path_is_not_live_privilege`, `test_docker_group_without_effective_root_is_not_live_privilege`, `test_effective_root_is_live_privilege_without_sudo_on_path` |
| Observe image used `@vantio/cli@^0.3.1`, copied the repo context, and ran `vantio run npm start`, which does not attach the Node interceptor | Reproduced. Exact pin `0.3.24`, strict `.dockerignore`, `vantio run node agent.js`. | `deploy/docker/test_observe_example.py` |
| `gate_get_policy` and `gate_residual_risk` accepted `api_key` and sent that value | Reproduced. The key is `VANTIO_API_KEY` only. Source version `@vantio/gate-mcp` `0.1.1` is a candidate, not a registry release. | `packages/vantio-gate-mcp/test/api_key_env.test.js` |

CLI `0.3.25` and Python `3.1.1` are not staged. Those packages were not changed. The observe example pins the CLI version already in this tree, `0.3.24`.

## Residual

`api_base` is still a tool argument on the two gate-mcp fetch tools. A caller can choose the URL that receives `VANTIO_API_KEY`. The key itself is no longer a tool argument.

An outside stage symlink was already refused by `confine` before this change. The reproduced hole was a symlink whose target stayed inside the stage parent.

`vantio-install` stays `0.1.0-stage-a`. That string is sealed.

## Verdict

| Field | Value |
| --- | --- |
| Council identity | independent read of tip `1bbed9021c9ceb494b34d1d3ab4d625d5e7c32f3` |
| Reviewer | not kvantio |
| Date | 2026-09-29 |
| Result | `PASS_WITH_NONBLOCKING_NOTES` |
| Notes | The four P1 fixes match the tests on that tip. `remove_stage` refuses a symlink with `lstat` and `O_NOFOLLOW` and leaves the target. Live mutations accept effective uid 0 only. The observe image pins `@vantio/cli@0.3.24` exactly and starts `vantio run node`. The gate-mcp tools no longer take `api_key`. Non-blocking: `api_base` is still a tool argument, so a caller can choose the URL that receives `VANTIO_API_KEY`. The Docker pin is a version string, not a digest. Opening the stage parent follows intermediate path components; the stage entry itself is not followed. |
