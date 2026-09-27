# Enterprise E1–E3 internal evaluator

INTERNAL | RECORD EVALUATOR | NOT SHIPPED | NO HOST CONTACT | NO CREDENTIALS | NO EXTERNAL IDENTITY | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification: `ENTERPRISE_E1_E3_INTERNAL_READY_FOR_COUNCIL`

This module evaluates customer-held governance records for ownership, delegation, and approval class. It does not enroll a host, create a credential, or contact Phantom Engine.

`schema_status` is `unstable-pre-1.0`. The package is private and is not in the pnpm workspace.

Notes: `docs/internal/enterprise-e1-e3/`.

```sh
node --test tests/enterprise-e1-e3/*.test.cjs
```
