# Architecture notes for the independent council

Audience: INTERNAL_RESTRICTED

Classification: `WAVE2_AUTHORITY_RECONCILED_READY_FOR_COUNCIL`

These notes are the design of the reconciliation. They are not a council verdict. Producer `bc-dc0c9f02-6053-5065-b948-8034e493f0e1` does not sit the council. `council.status` in the entry is `PENDING_INDEPENDENT_COUNCIL` and `council.verdict` is null.

## Question

The refresh packet at 2026-09-27T07:44:14Z recorded authority as that control plane understood it, against main `601342f08a59798ce207840cfb75293c3c22f45c`. Founder Wave 2 authorization dated 2026-09-27 names a later current authority, and Founder-accepted main `89f95099d0dce463307eb75d78e7fcf2ef99feb2` closes Wave 1 as the executable design foundation. The council is asked whether the added entry states that current authority and leaves the refresh packet intact.

## Shape

One entry lives at `docs/programs/production-readiness/authority/WAVE2-AUTHORITY.json`. Each of `MASTER-MANIFEST.json`, `WORKSTREAM-REGISTRY.json`, `DECISION-REGISTER.json`, and `RELEASE-REGISTER.json` carries the same `superseding_authority` pointer. The pointer is the only new key in those files. Truths are stored once, so the four registers cannot drift from each other.

The reading rule, copied in the pointer and in the entry:

> On a conflict, docs/programs/production-readiness/authority/WAVE2-AUTHORITY.json is the current authority. Earlier fields in this file remain the 2026-09-27T07:44:14Z refresh observation.

A reader who needs the refresh's own classification still reads `MASTER_CONTROL_PLANE_REFRESH_READY_FOR_COUNCIL` on the historical object. A reader who needs Founder authority on 2026-09-27 reads the entry.

## Why the historical sentences stay

`DEC-009`, the WS11 `NOT_RETRIEVED` slot, the WS1 writer hard stop, and the closed publish-workflow sentence are evidence of what the refresh believed. Deleting them would erase that observation. The entry names each sentence and the truth that governs the current reading. Tests require the historical JSON, with `superseding_authority` removed, to deep-equal the base commit.

Adjacent packets stay byte-identical on purpose. `COMPANY-GATES.json`, `DEMO-READINESS.json`, `demo/DEMO-MANIFEST.json`, `demo/10-WAVE2-SCAFFOLD.md`, and `DEPENDENCY-GRAPH.json` are refresh-era or design-era records. The Track 0 brief names the four registers. Editing the others would rewrite packets this force was told to leave.

## What the entry asserts

Ten truths, in brief order: Python 3.1.0 exact-hash publication `AUTHORIZED` with `hold` false; Units D and E on the `reader-compat` gate with `founder_blocked` false; O7 on the `option-c-revalidation` gate with `founder_blocked` false; investor-demo Wave 2 `AUTHORIZED_INTERNALLY`; I3 `AUTHORIZED_INTERNALLY` and `DISABLED` by default; Enterprise E1–E3 `AUTHORIZED_INTERNALLY` with live customer authority absent; WS11 `DEFINED` as R1–R18; stranger-host execution `BLOCKED` pending `named_host` and `named_operator`; announcements `HOLD`; Wave 1 `CLOSED_AS_EXECUTABLE_DESIGN_FOUNDATION` at the accepted main.

WS11 labels are one line each, taken from the Track 14 founder brief. Expanded specifications were not in that brief, and `expanded_specs_retrieved` is false. Formal SLSA, certification, proved reproducibility, and hardware-backed provenance stay false.

## What the entry refuses to conclude

- The reader-compat gate has passed. Pull request #81 is an ancestor of the accepted main. `gate_passed` is false.
- Option C revalidation has succeeded. `revalidation_adjudicated` is false. Gate 8 stays closed. No store file is created.
- I3 is enabled. `enabled` is false.
- Demo, pilot, or investor send is `READY`. `readiness_reclassified` is false.
- A new PyPI or npm observation was made. The wheel and sdist hashes are citations of `REL-PY-3.1.0`. `new_registry_observation` is false.
- WS11 process artifacts exist. `implemented` is false.
- Letters A–V received titles. `letters_titled` is false. WS0 stays untitled. WS4 is not redefined here.
- A host or an operator has been named for stranger-host execution.
- This classification is a council pass, or this pull request is merged.

## Grounds for a revision

The council should return the packet for revision if a truth contradicts the 2026-09-27 founder list, if a historical field was edited, if the four pointers differ, if R1–R18 labels were expanded or dropped, if `hold` is true for the 3.1.0 cut, if stranger-host execution or announcements are opened, if a provenance claim is set true, or if `gate_adjudicated`, `revalidation_adjudicated`, or `new_registry_observation` is true.
