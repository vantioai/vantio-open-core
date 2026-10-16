# Optics observation fragment

Audience: INTERNAL_RESTRICTED

Schema: `vantio.optics.observation-fragment` in `optics-observation-fragment.schema.json`.

`schema_status` is `unstable-pre-1.0`. This is not a stable schema and not a published package.

Optics observes. This fragment is a copy of bounded record fields. It does not block, redact, or cap a call. `enforcement_attached` is false. `claim_ceiling` is `OBSERVATION_ONLY`. `live_enforcement` is `NOT_APPLICABLE`.

## What crosses the repository boundary

Open-core builds the unsigned fragment with `src/fragment.cjs` and `src/fragment.py`. Those modules do not sign and do not import the Enterprise repository.

`vantio-enterprise-private` seals the fragment as `vantio.enterprise.evidence-export`. The seal code stays in that private repository. It checks this schema id, refuses an enforcement action, and does not treat the fragment as an allow.

## Digest

`record_sha256` is `sha256:` plus the hex digest of the canonical JSON of the fragment with `record_sha256` omitted. Canonical JSON is the evidence-contract encoding: sorted keys, no extra whitespace, integers only. A verifier removes `record_sha256`, canonicalizes the rest, and compares.

The Enterprise export then canonicalizes the whole fragment, including `record_sha256`, and signs those bytes with a test key. A production signing root is not created here.

## Call rule

A call whose `action` is `ALLOWED`, `REDACTED`, `BLOCKED`, or `DRY_RUN`, including a longer token that starts with `BLOCKED` or `DRY_RUN`, is `ENFORCEMENT_ACTION_EXCLUDED`. The fragment is not emitted. A missing action stays missing. It is not rewritten to `OBSERVED`.

`response_bytes` is an integer when the writer measured a size, and null when it did not. Null is not stored as zero.
