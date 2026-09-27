# @vantio/shared-health-runtime

PRIVATE | INERT | NOT SHIPPED | NO_LIVE_ENFORCEMENT | NO_OPTIMISTIC_GREEN | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

In-process producer and consumer for the twelve shared health states. The vocabulary catalog is the bound commit `c1de02538f66df94d58aef58bf0ec8459ae797ad`.

This package does not load Phantom Engine, does not change enforcement, and does not treat process liveness or HTTP 200 as a healthy token. `audit.green` stays false.

```bash
node --test tests/shared-health-runtime/*.test.cjs
```

Producer classification before council: `SHARED_HEALTH_RUNTIME_READY_FOR_COUNCIL`.
