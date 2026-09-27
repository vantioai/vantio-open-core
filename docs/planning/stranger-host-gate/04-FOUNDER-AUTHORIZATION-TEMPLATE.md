# Founder authorization template

```
NOT AUTHORIZED
DRAFT FOR A LATER FOUNDER FORCE
DO NOT EXECUTE
```

Audience: INTERNAL_RESTRICTED

This file is the copy-ready form for a later execution force. It does not authorize that force. The machine-checked copy is `authorization/FOUNDER-AUTHORIZATION.template.json`. The prep verifier requires every field below to stay at the prep values, including:

- `status`: `NOT_AUTHORIZED`
- `locked_main_sha`: `{{FOUNDER_LOCKED_MAIN_SHA}}`
- `host_class`: `{{FOUNDER_NAMED_HOST_CLASS}}`
- `host_owner`: `{{FOUNDER_NAMED_HOST_OWNER}}`
- `customer_host`: `FORBIDDEN`
- `credentials`: `NONE`
- `published_install_smoke`: `NO`
- `source_tree_ci_parity`: `UNFILLED`
- `assigns_evidence_tier`: false
- `assigns_stranger_host_proved`: false
- `gate_8`: `CLOSED`

Editing those values inside this packet makes the prep verifier fail. That is intentional. Authorization is a new force that copies this form, completes the placeholders, and replaces `scripts/refuse-stranger-host-execution.mjs`.

---

FOUNDER FORCE — WS3 P34 STRANGER-HOST EXECUTION (NOT AUTHORIZED)

## Locked starting state

Repository: `vantioai/vantio-open-core`

Prep packet that this force copies from:

`docs/planning/stranger-host-gate/`

Prepared against main (the prep record, already fixed):

`5064f32f1cdfcb840dfd100e2ce5c712d046550d`

Authorized checkout (Founder fills this when authorizing):

`{{FOUNDER_LOCKED_MAIN_SHA}}`

The execution agent verifies the checkout equals that SHA. On mismatch, stop with SH-STOP-05.

Host class (Founder names a Linux host with `strace`, outside the producer environment):

`{{FOUNDER_NAMED_HOST_CLASS}}`

Host owner (Founder names the operator of that machine):

`{{FOUNDER_NAMED_HOST_OWNER}}`

Customer host: `FORBIDDEN`

Credentials: `NONE`

Gate 8: `CLOSED`

## Matrix the Founder is choosing

Default, still unfilled in the prep template: source-tree CI parity from `.github/workflows/ci.yml`, commands in `05-RUNBOOK.md`.

Published install smoke: `NO` until the Founder writes `YES` in the later force and records a fresh registry observation for `@vantio/cli@0.3.24` and `vantio-agent-sdk==3.0.14`. The prep manual observation date is 2026-09-27 in `docs/products/optics/INSTALLATION.md`. The later force stops when the registry resolves a different version.

Evidence tier written by the execution force: `UNSET`

`assigns_stranger_host_proved`: false

## Session posture the later force sets before any command

- `HOME` is a new empty disposable directory
- `RUNNER_TEMP` is a new empty disposable directory
- `VANTIO_TELEMETRY_DISABLED=1`
- `DO_NOT_TRACK=1`
- `VANTIO_TELEMETRY`, `VANTIO_API_KEY`, `VANTIO_INGEST_URL`, `VANTIO_EXTRA_LLM_HOSTS`, `TARGET_URL`, `NPM_TOKEN`, `PYPI_TOKEN`, `TWINE_USERNAME`, `TWINE_PASSWORD`, and `NODE_AUTH_TOKEN` are unset

Phase 4 still runs the Python unittest suite, which calls `shield()`. The session posture above is what makes `send_run_telemetry_once` return before a send, except where `packages/vantio-agent-sdk-py/tests/test_telemetry.py` opts in and points `VANTIO_INGEST_URL` at a local `MockServer`. See SH-STOP-08. This template leaves live telemetry unauthorized.

## Explicit non-scope

Customer hosts. Credential creation. Live model-provider calls. Phantom Engine enrollment. Kernel or eBPF work. Operating-system package installation. `npm publish`, twine upload, tags, and GitHub releases. Editing product source. Opening Gate 8. Assigning `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. Mixing Python 3.1.0 source and published 3.0.14 in one interpreter. Workflows other than `.github/workflows/ci.yml`.

## Required return packet for that later force

- Host attestation
- Exact SHA
- Command transcripts and exit codes
- Env posture with presence only
- Disposable paths created
- `tier.txt` containing `UNSET`
- Confirmation the published smoke stayed off, or the separate virtualenv result if the Founder set it to `YES`
- Stop id if the run stopped

## Allowed final classifications for that later force

Exactly one of:

- `STRANGER_HOST_EVIDENCE_RECORDED_TIER_UNSET`
- `STRANGER_HOST_BLOCKED_NO_AUTH`
- `STRANGER_HOST_BLOCKED_HOST`
- `STRANGER_HOST_BLOCKED_SCOPE`
- `STRANGER_HOST_BLOCKED_CREDENTIAL`
- `STRANGER_HOST_BLOCKED_DIRTY_TREE`

This prep force’s classification stays `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`. The later classifications are names for a force that does not yet exist.

## Execution auth checklist required before that copy

`09-EXECUTION-AUTH-CHECKLIST.md` lists the names a later execution force writes into a copy of `authorization/EXECUTION-AUTH-CHECKLIST.template.json`. This packet keeps each one as a placeholder:

- `{{NAMED_HOST}}`
- `{{OWNER_OPERATOR}}`
- `{{DISTRO}}`
- `{{KERNEL}}`
- `{{ARCH}}`
- `{{CONTAINER_RUNTIME_PROFILE}}`
- `{{CONFIDENTIALITY_BOUNDARY}}`
- `{{ARTIFACT_ROUTE}}`
- `{{MAINTENANCE_WINDOW}}`
- `{{ROLLBACK_AUTHORITY}}`
- `{{INDEPENDENT_VERIFIER}}`
- `{{STOP_CONDITIONS}}`
- `{{FOUNDER_EXECUTION_AUTHORIZATION}}`

`execution_auth_checklist` on the machine template stays `UNFILLED`. `in_place_checklist_completion` stays `FORBIDDEN`. SH-STOP-21 is the stop when a run starts with any of those fields still unnamed.

---

End of template. Not authorized. Do not execute.
