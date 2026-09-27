# Verification instructions

Audience: INTERNAL_RESTRICTED

From the repository root:

```
node --test tests/governance-assurance/*.test.cjs
```

The package is private and is not a pnpm workspace member. Do not publish it.

A passing test run is a producer check of this catalog. It is not independent verification, not a clean-host proof, and not a stranger-host proof.

Reviewer for the mappings is PENDING_INDEPENDENT_COUNCIL. This force does not sit that council.

Regenerate the reports with the package `buildReports` function. The default clock is the catalog review instant, not a live wall clock.

Version rebind:

- 0.2.0 after Wave 2 merges that change a bound track.
- 0.3.0 after clean-host evidence exists.
- 0.4.0 after stranger-host execution is authorized and completed.
- 1.0.0-customer-candidate only after external assessment, disclosure review, and a separate release council.
