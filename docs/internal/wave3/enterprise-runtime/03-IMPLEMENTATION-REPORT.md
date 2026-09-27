# Implementation report

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_ENTERPRISE_RUNTIME_INTEGRATION_READY_FOR_COUNCIL`

## Added

- `internal/enterprise-runtime-integration/` — private composition module.
- `tests/enterprise-runtime-integration/` — direct, adversarial, and isolation tests.
- `docs/internal/wave3/enterprise-runtime/` — boundary, architecture, state separation, this report, the council slot, and the honesty registers.
- `docs/programs/production-readiness/wave3/ENTERPRISE-RUNTIME.md` and identical register copies.

## Registers

`RUNTIME-REGISTER.json`, `INTEGRATION-REGISTER.json`, and `STATUS.json` set:

- `record_layer_only` true
- `live_customer_authority` false and `customer_authority_promoted` false
- `wave2_close` `ENTERPRISE_E1_E3_INTERNAL_MERGED_RECORD_LAYER_ONLY_NO_LIVE_CUSTOMER_AUTHORITY`
- `host_attachment` false and `host_attachment_status` `HOST_ATTACHMENT_FALSE`
- `ebpf_loaded` false, `loader_mutated` false, `kernel_executed` false
- `active_protection` false
- `published` false, `announced` false, `frozen_version_reopened` false
- `credentials_issued` false
- `decision_reported_as_enforcement` false
- `contract_reported_as_kernel_enforcement` false
- `unattached_mechanism_reported_as_active_protection` false
- `clean_host_internal_proof` false and `proved_external` false
- `independent_verification_status` `NOT_INDEPENDENTLY_VERIFIED`
- `council_verdict` null
- EG-E2-8 and EG-E3-7 cited as `RECORD_LAYER_ONLY_HOST_UNSATISFIED`
- EG-E3-8 and EG-SUB-6 cited as `HOST_UNSATISFIED`

## Left unchanged

- `internal/enterprise-governance`
- `internal/pe-integrated-runtime`
- `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and Python `vantio-agent-sdk` `3.1.0`
- `pnpm-workspace.yaml`
- The Wave 2 packages and the Wave 3 PE registers

## Verification

`node --test tests/enterprise-runtime-integration/*.test.cjs`

That run reported 23 tests and 0 failures. The tests call the real record evaluator and the real PE runtime. An approved policy, an enroll intent, a cited policy version, a joint call with a PE deny, and a host-path contract leave both enforcement planes unapplied and `live_customer_authority` false.
