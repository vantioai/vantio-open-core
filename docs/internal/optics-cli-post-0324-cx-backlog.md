# OPTICS CLI POST-0.3.24 CX BACKLOG

Backlog only. Do not reopen, patch, republish, or retag @vantio/cli@0.3.24.

The Python SDK 3.1.0 customer lines (Optics status, observed outcome, provider response) are in `packages/vantio-agent-sdk-py`. This note is the deferred CLI refinement. It does not change the CLI package.

1. Replace primary human label "Application error" with precise observed outcomes
   (Provider authentication failed, Provider denied the request, Provider rate-limited
   the request, Provider service error, Connection to provider failed, Provider outcome unavailable, etc.).
2. Keep machine token APPLICATION_ERROR until a deliberate schema decision.
3. Rename displayed concept from "Application outcome" to "Observed outcome".
4. Show raw status separately: Provider response: HTTP 401 Unauthorized.
5. Make next actions outcome-aware: remediation first, inspection second, proof third.
6. Standardize next-action hierarchy across intercepted call output, run summary, tail, prove.
7. Do not patch 0.3.24 solely for this.
8. Schedule for the next intentional CLI customer-experience release.
