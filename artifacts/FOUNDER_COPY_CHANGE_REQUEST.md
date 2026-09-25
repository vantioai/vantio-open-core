# FOUNDER COPY CHANGE REQUEST
**Date:** 2026-09-23  
**Raised by:** Cloud Agent (Optics CLI closure run)  
**Status:** SUPERSEDED for Optics 0.3.21 by the Founder decision `RELEASE_PATH_2_LOGIN_RETIREMENT` (section at the end). The proposal below was not adopted.  
**Historical blocking note:** PR #45 was BLOCKED_AUTH before that decision.

---

## Context

The Optics CLI (`@vantio/cli`) includes `vantio login`, `vantio logout`, and `vantio whoami`
commands. These commands call the endpoint `GET https://vantio.ai/api/v1/config` with an
API key to validate the key and load policy. The production deployment status of this
endpoint has not been independently verified in this remediation run (classification:
`AUTH_DEPLOYMENT_UNVERIFIED`).

Per the Founder-approved brief:
> "if production deployment unverified/missing → do not claim login works; preserve
> account-free local Optics; remove login from primary quickstart; label
> unavailable/experimental ONLY if approved wording exists, else hide
> login/whoami/logout from public help while preserving internal compat if needed"

---

## Actions Taken (conservative path, no new unapproved wording)

The following changes were made in Phase 2 of this closure run:

1. **`vantio --help` (USAGE text in vantio.js):** `vantio login`, `vantio logout`,
   `vantio whoami` have been removed from the primary `vantio --help` USAGE listing.
   The commands remain functional — they still work when called directly.

2. **README.md Commands section:** `login`, `logout`, `whoami` have been moved from
   the primary command table to a sub-section titled "Account management (requires a
   trial key — see Step 3 above)". The Step 3 optional/trial language is unchanged.

3. **USAGE examples:** `vantio login vk_live_xxx` has been removed from the examples.

---

## Proposed Copy (AWAITING APPROVAL before use in public surfaces)

The following wording is proposed for the `vantio --help` output if the Founder
can confirm the production endpoint is deployed and login works for trial key holders:

```
Account (Phantom Engine / Enterprise trial key required):
  vantio login [key]          Save & validate your API key
  vantio logout               Remove the stored key
  vantio whoami               Show the stored key (masked) + connection status

  Get a key: hello@vantio.ai (trial) or vantio.ai/pricing (once self-serve is live).
  Free Optics — vantio run, prove, search, tail, diff, discover --local — needs no key.
```

---

## What Requires Founder Decision

1. **Is the production `/api/v1/config` endpoint deployed and accepting trial keys?**
   If YES: the proposed copy above can be adopted and login restored to public USAGE.
   If NO: current state (login hidden from USAGE, present in README as trial-only) is correct.

2. **Is the README Step 3 language approved for the current state?**
   Current Step 3 says: "Request a trial via hello@vantio.ai (or complete Stripe Checkout
   once self-serve billing is live — eng-shipped, keys not yet public)."
   If this language is approved, no change needed to README.

3. **Any specific approved wording for the auth-unavailable state?**
   e.g. "Login requires a Phantom Engine trial key. Free Optics needs no login."
   If approved, this can be used in the USAGE text.

---

## What Is NOT Changing Without Founder Approval

- No new unapproved wording will be added to any public-facing CLI output.
- Login/logout/whoami commands will NOT be re-added to USAGE without explicit approval.
- The README Step 3 "(optional)" framing will NOT be changed without approval.
- No production auth endpoint will be created or modified.

---

*This file will be superseded by the Founder's decision and should be removed or archived
once the auth copy question is resolved.*

---

## LOGIN RETIREMENT — 2026-09-23

Founder path: `RELEASE_PATH_2_LOGIN_RETIREMENT`.

Recorded facts:

- Production `GET /api/v1/config` on `https://vantio.ai` is source-only. The live host returns the marketing HTML 404. Classification remains `AUTH_ENDPOINT_SOURCE_ONLY`. This task did not deploy, repair, recreate, redirect, or replace that route.
- The Founder selected login retirement for Optics 0.3.21. Optics 0.3.21 is free, local-first, and account-free.
- Unsupported public copy for accounts, trial keys, dashboard sync, remote paid-tier synchronization, self-service billing, and Stripe Checkout was removed from the CLI help, usage errors, README, and package description.
- No "temporarily unavailable", "coming soon", outage, or return-date copy was added.
- This is a release-scope decision for Optics 0.3.21. It is not a plan for future authentication.

Compatibility, internal only:

- `vantio login` and `vantio whoami` are not dispatched. They print the unknown-command usage, which does not list them.
- `vantio logout` remains a hidden local file deletion of `~/.vantio/config.json`. It does not read or print the file and it does not use the network. Its stdout is only the approved identity and description.
- `vantio run`, `discover`, `prove`, `search`, `tail`, and `diff` do not read stored account config.
- A key in the environment does not fetch configuration or ingest from `vantio.ai` or `www.vantio.ai`.
- An explicit `VANTIO_INGEST_URL` on another host, with `VANTIO_API_KEY`, still loads policy from that control plane. That path is not documented as Optics 0.3.21 functionality.
- Telemetry stays off unless `VANTIO_TELEMETRY=1`. Opt-in posts to `/api/v1/telemetry` and does not call config or ingest.

Exact remaining package wording that is not the approved identity or description:

- README telemetry retention line, unchanged: `Retention: Unknown. Contact hello@vantio.ai for the data retention policy.` This is not an account-setup instruction. No new sentence was written for it.

No other public sentence is waiting on Founder copy for this retirement.
