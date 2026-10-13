# GAP-C8-VER-002 focused council

Audience: INTERNAL_RESTRICTED

| Item | Value |
| --- | --- |
| Verdict | `PASS_WITH_NOTES` |
| Merge | **ALLOWED** |
| PR | https://github.com/vantioai/vantio-open-core/pull/129 |
| Tip | `41d9215e80adeb0a7507aaf706f15c993304aa36` |
| Base | `e0278040790f70e796a057630efa0203fd8a00ed` (`main`) |
| Branch | `cursor/gap-c8-ver-002-settle-close-8032` |
| Authoring run | `bc-5528e38c-8808-5e77-b241-d11973648032` |
| Evidence run | `36506523073` (OVERALL FAIL) |
| Prepared policy SHA-256 | `2fd3909fe84cbe93b15c5525ece0d247d0f4f4a91e333346001d512e1efc5215` |

This is a source-only gate. It did not merge the pull request, dispatch a workflow, create AWS resources, or edit IAM.

Merge of this source is allowed. This verdict does not record `NONINTERACTIVE_TEARDOWN_READY`, does not authorize Class B, and does not record a billing close. A later destructive dispatch is a separate decision.

## What the diff does

Four files. The workflow change is a comment. Preflight is untouched. The verifier close order is instance, volume, EIP, security group, key pair.

1. Terminate the tagged instance, then poll until `terminated` (60 × 5s).
2. `DeleteVolume` when the tagged volume is `available` and has no attachments. `DetachVolume` is skipped on that path.
3. `ReleaseAddress` when the tagged EIP has no `AssociationId`. The CLI command `disassociate-address` is absent from the verifier.
4. Retry `DeleteSecurityGroup` on `DependencyViolation` (12 attempts; sleeps 5s, 10s, 15s, then 20s).
5. `DeleteKeyPair` only for `vantio-w3-class-b-lab-01`.

`DetachVolume` remains a last resort after the volume budget when the last observed state is `in-use` or `available`. The pull request body and README check 10 say so. A denied detach fails check 10 and does not call `DeleteVolume`.

## Blocking checklist

| Gate | Result |
| --- | --- |
| `Resource:*` Allow | Absent. The string appears only in failure text that refuses a widen. |
| IAM document or policy SHA change | Absent. Digest stays `2fd3909f…`. |
| Live fixture ids on the default dry path | Absent. `run_destructive_fixtures` defaults false. With the flag false, passed ids are ignored and no close API is called. |
| Sentinel `TerminateInstances --dry-run` restored | Absent. Checks 4 and 8 still use `CreateSecurityGroup --dry-run`. `i-0deadbeef0deadbee` is absent from the verifier. |
| NotFound accepted as an authorization pass | Absent for checks 4, 8, 10, 11, and 13. See note A for check 9. |
| Ready / Class B claim | The summary states Class B is not authorized and that the run does not record `NONINTERACTIVE_TEARDOWN_READY`. The JSON report has no readiness flag. |
| Deny probes removed | Checks 4, 5, 6, 7, and 8 are unchanged. |
| Unbounded wait | Budgets are finite: instance 300s, volume 120s, post-detach 60s, EIP 120s, security-group sleeps 190s. Stacked sleeps are 790s, inside the verify job's 20 minute timeout. Exhausted volume, EIP, and security-group waits fail the check. |
| Delete without a tag or name check | Instance, volume, EIP, and security group are described and tag-checked before a destructive call. The default security group is refused. The key pair is refused unless the name is exactly `vantio-w3-class-b-lab-01`. |

## Seats

**GitHub Actions / OIDC.** `workflow_dispatch` only. Permissions stay `contents: read` and `id-token: write`. Preflight still has no environment and no `id-token`. Verify still needs preflight, uses environment `w3-lab-teardown`, role `arn:aws:iam::960577828987:role/vantio-w3-lab-teardown`, account `960577828987`, audience `sts.amazonaws.com`, and `role-duration-seconds` 3600. The identity step still requires `refs/heads/main`.

**EC2 settle.** The happy path matches the failed run's cause: terminate was accepted while the volume was still attached and the EIP was still associated, so `DetachVolume` and `DisassociateAddress` were evaluated against the instance ARN and the network-interface ARN. Those calls are no longer on the path that sees `available` and a cleared association. `DependencyViolation` is retried and is described as a residual dependency.

**Blast radius.** Closes run only when the dispatch flag is true and an id was passed. Format checks refuse malformed ids before any API call. Tag mismatch refuses the instance, volume, EIP, and security group with no mutate call. No snapshot API is present.

## Notes (non-blocking)

**A. Instance settle is a poll, then later closes still run.** If the instance stays `shutting-down` for the whole 300s budget, check 9 stays `PASS` because `TerminateInstances` was accepted. A local fake of that path called `detach-volume` once, did not call `delete-volume` or `disassociate-address`, retried `delete-security-group` 12 times, deleted the authorized key pair, and returned OVERALL FAIL. README check 9 says the wait finishes before the volume, EIP, and security-group closes. The code's real gates are the per-resource checks.

**B. `DetachVolume` is still reachable.** After 24 × 5s, state `in-use` or `available` with attachments calls `detach-volume --volume-id`. Under the locked policy that call is the check 10 failure from run `36506523073`. The verifier records `UnauthorizedOperation`, does not widen IAM, and does not delete. A volume that stays `available` with a leftover attachment record takes this same failure and is left in place.

**C. EIP that stays associated fails closed.** After 24 × 5s the check fails, names the association id, and calls neither `DisassociateAddress` nor `ReleaseAddress`.

**D. One post-terminate `InvalidInstanceID.NotFound` leaves check 9 `PASS`.** The detail says NotFound is not a pass. The pass predicate is the accepted terminate. A local fake with that NotFound and an already-free tagged volume deleted the volume and returned OVERALL PASS. Volume, EIP, and security-group NotFound during their own closes fail those checks and do not delete or release.

**E. Enabling `DetachVolume` on `instance/*` later (GAP-C8-IAM-002) would make the last-resort path live.** This pull request does not apply that policy change. A future narrow add should be re-counciled against this call site.

## Tests

Local, no AWS calls, on tip `41d9215`:

- `scripts/aws/test_verify_w3_lab_teardown.py`: 51 tests, OK
- `scripts/aws/test_w3_lab_teardown_workflow.py`: 5 tests, OK
- `scripts/aws/test_preflight_w3_lab_teardown.py`: 10 tests, OK

GitHub Actions run `36512578468` on that tip already completed. The job `Release governance contract`, which runs those three modules, succeeded. This council did not dispatch `w3-lab-teardown-verify.yml`.
