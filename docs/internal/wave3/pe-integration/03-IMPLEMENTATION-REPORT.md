# Implementation report

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`

## Added

- `internal/pe-integrated-runtime/` — private composition module.
- `tests/pe-integrated-runtime/` — direct, adversarial, and isolation tests.
- `docs/internal/wave3/pe-integration/` — boundary, architecture, state separation, this report, the council slot, and the honesty registers.
- `docs/programs/production-readiness/wave3/` — program boundary, reading note, status, and identical register copies.

## Registers

`RUNTIME-REGISTER.json` and `INTEGRATION-REGISTER.json` set:

- `host_attachment` false and `host_attachment_status` `HOST_ATTACHMENT_FALSE`
- `ebpf_loaded` false, `loader_mutated` false, `kernel_executed` false
- `active_protection` false
- `decision_reported_as_enforcement` false
- `contract_reported_as_kernel_enforcement` false
- `unattached_mechanism_reported_as_active_protection` false
- `clean_host_internal_proof` false and `proved_external` false
- `independent_verification_status` `NOT_INDEPENDENTLY_VERIFIED`
- `council_verdict` null

## Left unchanged

- `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and Python `vantio-agent-sdk` `3.1.0`
- `pnpm-workspace.yaml`
- The Wave 2 packages themselves
- Governance evidence indexes. Those indexes record an earlier catalog. This force adds its own registers rather than rewriting that catalog.

## Verification

`node --test tests/pe-integrated-runtime/*.test.cjs`

The tests call the real evaluators. They check that a cited deny, an application `BLOCKED_HOST` label, a held ingress decision, a progressive `PROMOTED_MATCH`, and a `HEALTHY_ENFORCING` token leave `applied` false on both enforcement planes.
