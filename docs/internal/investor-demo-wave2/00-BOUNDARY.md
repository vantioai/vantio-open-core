# Investor demo Wave 2 boundary

Audience: INTERNAL_RESTRICTED

Producer classification: `INVESTOR_DEMO_WAVE2_READY_FOR_COUNCIL`

This classification means the branch is ready for a separate council. It is not a council verdict, not a customer demonstration, and not `PROVED_EXTERNAL`.

## Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Design tip | `43cc35371e109e6a377cc31e4fd2438bfceea797` |
| Design merge | pull request #75, commit `62379ca40ee18d04dd24af815b13a32b84be4001` |
| CLI | `@vantio/cli@0.3.24`, not reopened |
| Founder beat text | `ABSENT`. B01–B18 stay the room sequence |
| Announcements | `HOLD` |

## What this force writes

- `packages/investor-demo-wave2/` — private runner, not a workspace member, not a published CLI
- `tests/investor-demo-wave2/` — direct and adversarial tests
- `docs/internal/investor-demo-wave2/` — this packet

## What this force does not do

- It does not edit `packages/vantio-cli` or any other published package.
- It does not bump, tag, publish, or announce.
- It does not run Phantom Engine, enroll a host, load a kernel program, or call a live provider.
- It does not write `LOCAL_OBSERVATION` or count a simulated row as customer activity.
- It does not write enforcement action tokens into a run file.
- It does not copy the design envelope into `~/.vantio/runs/`.
- It does not change the design directory under `docs/programs/production-readiness/demo/`.
- It does not merge.

## Proof

Every card carries a proof class from this set: `INTERNAL_FUNCTIONAL`, `SIMULATED_LABELED`, `NARRATED_BOUNDARY`, `OFFLINE_FALLBACK`, `HELD_NOT_EXECUTED`.

Every card carries `external_proof` `NOT_PROVED_EXTERNAL`. Evidence tier and customer validation stay `UNSET`.

`INVESTOR_DEMO_WAVE2_READY_FOR_COUNCIL` is assigned only after uninstall of the recorded demo home succeeds and the local verifier accepts the export. Visual completion does not assign it. `INVESTOR_DEMO_WAVE2_AWAITING_UNINSTALL` is the pre-uninstall classification when the other checks passed. A failed check is `INVESTOR_DEMO_WAVE2_BLOCKED`.
