# INTERNAL_RESTRICTED — C8 teardown role verification

Audience: INTERNAL_RESTRICTED

This note is the dispatch and protection record for the GitHub Actions OIDC check of `vantio-w3-lab-teardown`. It does not authorize Class B, a Paid plan change, or a new host.

A passing run is the verification that the role can be assumed and that the probes below behaved as expected. This note does not itself prove the role is present in AWS.

## Role

| Item | Value |
| --- | --- |
| Role ARN | `arn:aws:iam::960577828987:role/vantio-w3-lab-teardown` |
| Account | `960577828987` |
| OIDC provider | `token.actions.githubusercontent.com` |
| Trust action | `sts:AssumeRoleWithWebIdentity` |
| Trust subject | `repo:vantioai/vantio-open-core:environment:w3-lab-teardown` |
| Audience | `sts.amazonaws.com` |
| Region | `us-east-2` |
| Max session | 3600 seconds |
| Prepared policy SHA-256 | `2fd3909fe84cbe93b15c5525ece0d247d0f4f4a91e333346001d512e1efc5215` |
| Key pair name in that policy | `vantio-w3-class-b-lab-01` |

The SHA-256 above is a prepared digest of the policy document after the key pair name was substituted to `vantio-w3-class-b-lab-01`. It is not a live-measured hash from IAM. This repository does not store that policy JSON. The workflow does not call `iam:GetRole`. Check 2 records MaxSessionDuration as 3600 from this handoff and fails unless the assume step returns an STS Expiration at most one hour ahead.

The workflow does not create a long-lived access key, an IAM user, or a root key. The job refuses to start the assume step if `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `AWS_SESSION_TOKEN` is already set. `use-existing-credentials` is false, so ambient credentials cannot skip the OIDC exchange.

`configure-aws-credentials` v6 emits the STS Expiration only when credential outputs are enabled. The assume step turns that on so check 2 can record Expiration. The verify step reads `aws-expiration`, `aws-account-id`, and `authenticated-arn`. It does not read the secret credential outputs.

## GitHub environment

Name: `w3-lab-teardown`.

The Founder must create this protected environment BEFORE any dispatch. GitHub auto-creates an unprotected environment when a job that sets `environment:` is scheduled and that name does not already exist. An unprotected environment has no required reviewers and no branch rule, and a job that reaches it can assume the role. The trust policy checks the environment subject. It does not check GitHub's protection rules.

Creation was attempted on 2026-09-28 with the repository integration token:

```text
PUT /repos/vantioai/vantio-open-core/environments/w3-lab-teardown
```

GitHub returned `403 Resource not accessible by integration`. That call did not create the environment. Do not dispatch this workflow to "see if the environment appears."

If an unprotected `w3-lab-teardown` environment was created by a dispatch, delete it before creating the protected one:

```bash
gh api --method DELETE repos/vantioai/vantio-open-core/environments/w3-lab-teardown
```

Delete only the accidental unprotected environment. After it is gone, create the protected environment. The protected publish environments `npm-publish`, `pypi`, and `mcp-registry-publish` already use this pattern:

- required reviewer GitHub login `zacharybalicki` (user id `269605088`)
- `prevent_self_review: false` (a single reviewer can approve a run they started; the sibling environments use this)
- custom deployment branch policy allowing only `main`

`zacharybalicki` must remain a required reviewer. Other reviewers may be added beside that user. `prevent_self_review` stays false so the publish-environment pattern does not deadlock a single reviewer.

```bash
gh api --method PUT repos/vantioai/vantio-open-core/environments/w3-lab-teardown --input - <<'JSON'
{
  "wait_timer": 0,
  "prevent_self_review": false,
  "can_admins_bypass": true,
  "reviewers": [
    {"type": "User", "id": 269605088}
  ],
  "deployment_branch_policy": {
    "protected_branches": false,
    "custom_branch_policies": true
  }
}
JSON

gh api --method POST \
  repos/vantioai/vantio-open-core/environments/w3-lab-teardown/deployment-branch-policies \
  --input - <<'JSON'
{"name": "main", "type": "branch"}
JSON
```

The `preflight` job does not set `environment:`. It GETs the environment and fails unless the environment exists, `zacharybalicki` (id `269605088`) is a required reviewer, and the deployment branch policy allows only `main`. The `verify` job is the only job that sets `environment: w3-lab-teardown`, and it has `needs: preflight`. A failed preflight skips `verify`, so that skipped job does not schedule the environment. Both jobs also require `GITHUB_WORKFLOW_REF` to be `vantioai/vantio-open-core/.github/workflows/w3-lab-teardown-verify.yml@refs/heads/main`.

## Dispatch

After this workflow file is on `main` and the protected environment already exists, open Actions, choose **Verify W3 lab teardown role**, and run it on `main`. Leave fixture close off unless the ids of an already-provisioned disposable lab are in hand.

`verify` waits for the environment reviewer before the OIDC assume.

```bash
gh workflow run w3-lab-teardown-verify.yml --ref main \
  -f run_destructive_fixtures=false
```

Destructive close is limited to the ids passed at dispatch. The verifier describes each id in `us-east-2` and refuses the call when the tags do not match the authorized fixture. The key pair input is accepted only when it is exactly `vantio-w3-class-b-lab-01`. Close order is EIP, instance, volume, security group, then key pair, so a group delete is not attempted while the instance is still associated. Reported check numbers stay 9 instance, 10 volume, 11 security group, 12 key pair, 13 EIP.

```bash
gh workflow run w3-lab-teardown-verify.yml --ref main \
  -f run_destructive_fixtures=true \
  -f fixture_instance_id=i-0123456789abcdef0 \
  -f fixture_volume_id=vol-0123456789abcdef0 \
  -f fixture_security_group_id=sg-0123456789abcdef0 \
  -f fixture_keypair_name=vantio-w3-class-b-lab-01 \
  -f fixture_eip_allocation_id=eipalloc-0123456789abcdef0
```

Those example ids are placeholders. Pass only real disposable fixture ids.

Checks 9–13 stay `NOT_RUN_AWAITING_FIXTURES` when the flag is false, or when the flag is true and that id was not passed. That status does not fail the job.

## What the job checks

The log prints `CHECK NN STATUS name: detail`. The same rows are in the job summary and in the artifact `w3-lab-teardown-verify-<run_id>` (`w3-lab-teardown-verify.json`). The artifact field `policy_sha256` is labeled `prepared_digest`. It is not a live-measured hash. The job fails when any check is `FAIL`.

1. `sts get-caller-identity` shows account `960577828987` and role `vantio-w3-lab-teardown`.
2. Requested session duration is 3600 seconds or less, and the assume step returned an STS Expiration. A missing Expiration is a fail. Remaining lifetime must be at most one hour plus two minutes of clock skew.
3. `DescribeInstances` in `us-east-2` with the lab tag filters (`vantio:program=w3-clean-host-lab`, `vantio:lifecycle=lab`, `vantio:destroyable=true`, `vantio:environment=lab`). Zero instances is a pass. `AccessDenied` is a fail.
4. `CreateSecurityGroup --dry-run` in `us-east-2` for `vantio-w3-teardown-verify-tagged-deny-probe`, with the lab tags (`vantio:program=w3-clean-host-lab`, `vantio:lifecycle=lab`, `vantio:destroyable=true`, `vantio:environment=lab`). The `--tag-specifications` value is one JSON object that starts with `{`, which is the form AWS CLI v2 parses as JSON and sends to EC2. `AccessDenied` or `UnauthorizedOperation` is a pass. `DryRunOperation`, or a call that returns a group id, is a fail, because the create would have been allowed. The default path does not call `TerminateInstances` and does not delete a group. `NotFound`, any code ending in `NotFound`, `NotFoundException`, and `ResourceNotFoundException` fail this check, including when the message contains `explicit deny` or `not authorized`. Those codes mean the named resource does not exist. Run `36474749760` (GAP-C8-VER-001) returned `InvalidInstanceID.NotFound` for `TerminateInstances --dry-run` on sentinel `i-0deadbeef0deadbee` in `us-east-2`. This role is allowed to call `ec2:TerminateInstances` when the lab tags match, and EC2 answers a missing instance id with `NotFound` instead of `DryRunOperation` or `UnauthorizedOperation`. The verifier uses this tagged create dry-run for that reason. A pass means the create was denied. It does not measure the tag condition on `ec2:TerminateInstances`. `iam:SimulatePrincipalPolicy` is not called. This role is not granted that action, and this workflow does not add it.
5. `CreateSecurityGroup --dry-run` in `us-east-2` for `vantio-w3-teardown-verify-deny-probe`, without those tags. The expected result is `AccessDenied` or `UnauthorizedOperation`. `DryRunOperation` is a fail. `RunInstances` is not called. A group id is not deleted by this check. `NotFound` fails this check.
6. `iam:GetUser` for the nonexistent name `vantio-w3-teardown-verify-deny-probe`. The expected result is `AccessDenied`. `CreateUser` is not called.
7. `ce:GetCostAndUsage` (Cost Explorer lives in `us-east-1`). The expected result is `AccessDenied`. The probe does not change a support plan or payment method.
8. `DescribeInstances` in `us-east-1`, and `CreateSecurityGroup --dry-run` there for `vantio-w3-teardown-verify-region-deny-probe`. Both must be denied with `AccessDenied` or `UnauthorizedOperation`. `DryRunOperation`, or a call that returns a group id, is a fail. `NotFound`, any code ending in `NotFound`, `NotFoundException`, and `ResourceNotFoundException` fail this check on either call, including when the message contains `explicit deny` or `not authorized`. The default path does not call `TerminateInstances`. On run `36474749760`, describe in `us-east-1` was denied and the sentinel `TerminateInstances --dry-run` returned `InvalidInstanceID.NotFound`, so that terminate result did not prove the region boundary.
9. Terminate the passed instance, only when destructive close is on and the id's tags match.
10. Detach, if needed, and delete the passed volume when its tags match, including `vantio:owned-by=transaction`.
11. Delete the passed security group when its tags match.
12. Delete the key pair only when the name is `vantio-w3-class-b-lab-01`.
13. Disassociate, if needed, and release the passed EIP when its tags match.
14. `cloudtrail:LookupEvents` in `us-east-2` for this session. A successful call with zero events is a pass; ingestion can lag.
15. `DOCUMENTED`. The STS Expiration is recorded. The job cannot prove the credentials are dead before that timestamp. The credentials action clears the environment variables when the job ends.

## What this does not do

- It does not provision a Class B lab or any other host.
- It does not create IAM users, access keys, or root keys. Check 6 is `iam:GetUser` on a probe name. It does not call `CreateUser`.
- It does not change billing, payments, or the Paid plan.
- It does not grant `NONINTERACTIVE_TEARDOWN_READY`.
- It does not record `STAGE_B_BILLING_CLOSE_PASS`.

Class B remains unauthorized until both `STAGE_B_BILLING_CLOSE_PASS` and `NONINTERACTIVE_TEARDOWN_READY` are actually recorded. The governance record in this repository still has billing at `STAGE_B_BILLING_CLOSE_PENDING`, and C8 is not `NONINTERACTIVE_TEARDOWN_READY`. A green run of this workflow does not flip those tokens.
