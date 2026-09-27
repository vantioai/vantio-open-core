# @vantio/pe-sequential-authority

INTERNAL_CANDIDATE | EVALUATE_ONLY | NOT_HOST_ENFORCEMENT | NOT_SHIPPED | NO_KERNEL | NO_ENROLL | NO_CREDENTIAL_MATERIAL | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Private evaluate-only candidate for authority that spans more than one otherwise allowed action. Version `0.0.0-unstable-pre-1.0`. `schema_status` `unstable-pre-1.0`.

Producer classification: `PE_SEQUENTIAL_AGGREGATE_AUTHORITY_READY_FOR_COUNCIL`

That classification is ready for a separate council. It is a producer handoff. Council status stays `PENDING_INDEPENDENT_COUNCIL`.

The package is outside `pnpm-workspace.yaml`. It does not enroll a host, load a kernel program, open a socket, or store credential material.

```sh
node --test tests/pe-sequential-authority/*.test.cjs
```

Notes: `docs/internal/pe-sequential-authority/`.
