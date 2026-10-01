# Optics audit P1 independent council

Audience: review of source changes on this branch.

Status: `PENDING_INDEPENDENT_COUNCIL`

`council_pass`: false

`merge_state`: `WAITING_FOR_AUTHORIZED_REVIEWER`

Publication: `CANDIDATE_ONLY_NOT_FOR_PUBLICATION`. No npm publish, no PyPI publish, no install.vantio.ai go-live.

The producer wrote this packet and the tests. The producer does not sit this council and does not fill the verdict. Approval has to come from kvantio, and the author of the change is not that reviewer.

## Packet

| Finding | Result | Tests |
| --- | --- | --- |
| Installer `remove_stage` followed a stage symlink that stayed inside the parent, then `shutil.rmtree` raised instead of refusing | Reproduced. Removal now `lstat`s the stage, opens it with `O_NOFOLLOW`, and refuses a symlink. Child symlinks are unlinked. Their targets stay. | `tests.test_live_executor.LiveExecutorTests.test_remove_stage_refuses_symlink_and_does_not_follow_it`, `test_remove_stage_does_not_follow_a_symlink_inside_the_directory`, `test_fixture_remove_stage_refuses_symlink` |
| `_privilege_ok` treated `sudo` on `PATH`, and a docker-group socket writer, as a live grant | Reproduced. Live apply, rollback, and uninstall require effective uid 0. | `test_sudo_on_path_is_not_live_privilege`, `test_docker_group_without_effective_root_is_not_live_privilege`, `test_effective_root_is_live_privilege_without_sudo_on_path` |
| Observe image used `@vantio/cli@^0.3.1`, copied the repo context, and ran `vantio run npm start`, which does not attach the Node interceptor | Reproduced. Exact pin `0.3.24`, strict `.dockerignore`, `vantio run node agent.js`. | `deploy/docker/test_observe_example.py` |
| `gate_get_policy` and `gate_residual_risk` accepted `api_key` and sent that value | Reproduced. The key is `VANTIO_API_KEY` only. Source version `@vantio/gate-mcp` `0.1.1` is a candidate, not a registry release. | `packages/vantio-gate-mcp/test/api_key_env.test.js` |

Source candidates `@vantio/cli` `0.3.25` and Python `vantio-agent-sdk` `3.1.1` are staged in this tree. They are not npm or PyPI releases. The observe example still installs published CLI `0.3.24`.

## Residual

`api_base` is still a tool argument on the two gate-mcp fetch tools. A caller can choose the URL that receives `VANTIO_API_KEY`. The key itself is no longer a tool argument.

An outside stage symlink was already refused by `confine` before this change. The reproduced hole was a symlink whose target stayed inside the stage parent.

`vantio-install` stays `0.1.0-stage-a`. That string is sealed.

## Verdict

| Field | Value |
| --- | --- |
| Council identity | `PENDING` |
| Reviewer | `PENDING` — kvantio, non-author |
| Date | `PENDING` |
| Result | `PENDING` |
| Notes | `PENDING` |
