# No optimistic defaults

INTERNAL_CANDIDATE | EVALUATE_ONLY | NOT_HOST_ENFORCEMENT | NOT_SHIPPED | NO_KERNEL | NO_ENROLL | NO_CREDENTIAL_MATERIAL | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

The evaluator fills nothing in that would widen authority.

- A missing ceiling, window, principal, or authority source is `INPUT_REJECTED`.
- `redelegation` must be the string `forbidden`. Any other value is rejected.
- An empty action list, destination list, credential list, or node list authorizes nothing in that list.
- An omitted consensus list is not an approval. A present consensus list is ignored when the source is the envelope, and it is rejected when it is the source.
- An omitted process-to-principal flag does not create a principal. Setting the flag denies.
- An omitted receipt is not a bearer token. Presenting a receipt denies a new step.
- Reserved rights are absent from a child. They are not inferred from a parent list.
- A denied step leaves consumption where it was.
- Unknown keys on the envelope, the step, and the evaluate input are rejected, including keys that would claim host attachment or a doctrine verdict.

Omitted optional step fields normalize to null or false. False on `raises_ceiling` means the step does not ask for a raise. It does not grant a raise.
