# Execution authorization checklist

Audience: INTERNAL_RESTRICTED

Status: `UNFILLED`

Execution status: `NOT_AUTHORIZED`

Machine copy: `authorization/EXECUTION-AUTH-CHECKLIST.template.json`

In-place completion: `FORBIDDEN`

This checklist is the named host and operator gate for any future stranger-host execution authorization. The prep Founder template in `04-FOUNDER-AUTHORIZATION-TEMPLATE.md` stays unfilled. Filling either file inside this packet fails verification. A later Founder force copies both files, replaces every placeholder with a named value, and replaces `scripts/refuse-stranger-host-execution.mjs`. Until that force exists, the refuse script exits 2.

## Required names

| Field | Placeholder | What the later copy records |
| --- | --- | --- |
| Named host | `{{NAMED_HOST}}` | The machine the Founder names for the run |
| Owner/operator | `{{OWNER_OPERATOR}}` | The owner and the operator of that machine |
| Distro | `{{DISTRO}}` | Distribution name on that machine |
| Kernel | `{{KERNEL}}` | Kernel release on that machine |
| Arch | `{{ARCH}}` | Architecture of that machine |
| Container/runtime profile | `{{CONTAINER_RUNTIME_PROFILE}}` | Container runtime and profile, or the explicit bare-host profile |
| Confidentiality boundary | `{{CONFIDENTIALITY_BOUNDARY}}` | What data and repos the run is allowed to touch |
| Artifact route | `{{ARTIFACT_ROUTE}}` | Where the evidence bundle is written and who can read it |
| Maintenance window | `{{MAINTENANCE_WINDOW}}` | The window the operator may use |
| Rollback authority | `{{ROLLBACK_AUTHORITY}}` | Who may delete the disposable paths in `06-ROLLBACK.md` |
| Independent verifier | `{{INDEPENDENT_VERIFIER}}` | Who reviews the bundle after the run |
| Stop conditions | `{{STOP_CONDITIONS}}` | The stop set for that run, including SH-STOP-01 through SH-STOP-21 |
| Founder execution authorization | `{{FOUNDER_EXECUTION_AUTHORIZATION}}` | The Founder authorization record for that run |

Customer host stays `FORBIDDEN`. Credentials stay `NONE`. `assigns_evidence_tier` stays false. `assigns_stranger_host_proved` stays false.

## Gap rule

A future authorization still has gaps while any field remains a placeholder, the checklist is this in-packet copy, the refuse script exits 2, the Founder status is `NOT_AUTHORIZED`, the authorization is uncopied, the host is a customer host, a credential is present, or an evidence tier is assigned. `scripts/readiness-lib.mjs` exports `executionAuthGaps` for that rule. An empty gap list is an input a later force would still have to act on. This packet's verifier requires the in-packet fields to stay placeholders, so the gap list for this copy stays non-empty. The readiness command has no branch that starts a host when the gap list is empty.
