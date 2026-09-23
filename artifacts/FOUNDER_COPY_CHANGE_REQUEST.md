# FOUNDER COPY CHANGE REQUEST
**Date:** 2026-09-23  
**Raised by:** Cloud Agent (Optics CLI closure run)  
**Status:** AWAITING FOUNDER REVIEW — no change to public-facing copy without approval  
**Blocking:** PR #45 final verdict cannot be upgraded to PASS until auth surface copy is resolved

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
