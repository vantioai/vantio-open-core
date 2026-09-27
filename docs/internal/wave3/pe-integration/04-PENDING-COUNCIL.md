# Pending council

Audience: INTERNAL_RESTRICTED

| Field | Value |
| --- | --- |
| `council_status` | `PENDING_INDEPENDENT_COUNCIL` |
| `council_verdict` | null |
| `self_certified_council_pass` | false |
| Producer classification | `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL` |

This slot is empty. The producer classification means the source composition is ready for a separate council. It does not record a council pass.

This force does not claim `CLEAN_HOST_INTERNAL_PROOF` or `PROVED_EXTERNAL`.

Tracks that attach a host or load a program are outside this composition. Until those tracks exist and a separate council accepts them, the execution ceiling remains `CONTRACT_ONLY`, `EVALUATE_ONLY`, and `HOST_ATTACHMENT_FALSE`.
