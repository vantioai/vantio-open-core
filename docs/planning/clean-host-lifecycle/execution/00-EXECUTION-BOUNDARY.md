# Clean-host lab execution — program boundary

Audience: INTERNAL_RESTRICTED

Producer role: execution producer only. This agent does not sit the independent council, does not self-assign a council pass, and does not assign an evidence tier.

Producer identity: Cursor cloud agent `bc-36ae62af-00aa-561d-ba4e-e99dd8ea62cc`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-36ae62af-00aa-561d-ba4e-e99dd8ea62cc

Producer classification: `CLEAN_HOST_BLOCKED_INFRA_READY_FOR_COUNCIL`

Environment class: `CLEAN_HOST_INTERNAL_PROOF`

That classification means the required proof sequence could not run on a clean host, the missing prerequisites are recorded, and the packet is ready for a separate council. It is a producer handoff. Council status stays `PENDING_INDEPENDENT_COUNCIL`.

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Commit subject | Merge pull request #83 from `vantioai/cursor/pe-ws4-vocabulary-binding-f9f5` |
| Merged design | `docs/planning/clean-host-lifecycle/` at `2bff8ceb6ba0e3d5a3083c51f14051de72e5fd2c` (pull request #76) |
| Design producer classification | `CLEAN_HOST_LAB_DESIGN_READY_FOR_COUNCIL` |
| Branch for this packet | `cursor/clean-host-lab-execution-62cc` |
| Writable path | `docs/planning/clean-host-lifecycle/execution/` |
| Evidence tier | `UNSET` |
| Stranger-host | `NOT_RUN` |
| Phantom-Box | `EXCLUDED` |
| Customer validation | `UNSET` |
| Independent verifier | `UNSET` |

## 2. What this force does

- Re-runs the merged design exerciser `scripts/check-guards.sh` on the producer pod and records the process result.
- Probes the same pod for the host prerequisites the required sequence needs.
- Records each required sequence row as `BLOCKED_INFRA` with the missing prerequisite.
- Leaves `05-INDEPENDENT-COUNCIL.md` as `PENDING_INDEPENDENT_COUNCIL`.

The exerciser exit code is a process result for the merged script contract. It leaves `evidence_tier` at `UNSET`. It does not fill a sequence row.

## 3. Required sequence

The sequence is: clean baseline, compatibility, artifact verify, install, observe, ingress, egress, allowed, denied, app/host correlation, proposal, simulation, canary, enforcement, restart, reboot, degradation, recovery, evidence export, revocation, rollback, upgrade, uninstall, residual inspection.

Every row in `02-SEQUENCE-MATRIX.md` is `BLOCKED_INFRA`. The selected producer classification is `CLEAN_HOST_BLOCKED_INFRA_READY_FOR_COUNCIL`.

## 4. What this force keeps closed

- Product code, package versions, workflows, tags, GitHub releases, npm, and PyPI.
- CLI `0.3.24` reopen. The in-tree version field was read. The package was not packed, published, or bumped.
- Python `3.1.0` byte mutation. The published Python package was not invoked.
- Phantom Engine load, `bpftool`, a kernel verifier run, and `cargo build` of Phantom crates.
- Docker, `kind`, image pull, GHCR inspection, Helm install, and DaemonSet apply.
- Stranger-host execution, customer hosts, and customer deploy.
- Credential creation, money movement, and announcements.
- Phantom-Box. `VANTIO_SOAK_LOCAL` stayed unset. Nothing was read from a local control plane on port `5001`.
- Evidence-tier assignment, including any edit to the traceability matrix.
- Public manuals and confidential Phantom customer-manual bodies.
- A reboot of this pod.

## 5. Classification fields this packet writes

| Field | Value |
| --- | --- |
| `producer_classification` | `CLEAN_HOST_BLOCKED_INFRA_READY_FOR_COUNCIL` |
| `environment_class` | `CLEAN_HOST_INTERNAL_PROOF` |
| `evidence_tier` | `UNSET` |
| `stranger_host` | `NOT_RUN` |
| `phantom_box` | `EXCLUDED` |
| `customer_validation` | `UNSET` |
| `independent_verifier` | `UNSET` |
| `requirement_status_label` | `INTERNAL_PROOF` |

`INTERNAL_PROOF` is the lab requirement-status label from the merged design. It is not an evidence tier. This packet does not write it into `docs/architecture/optics-foundation/TRACEABILITY-MATRIX.json`.

Assigned evidence tier is `UNSET`. This packet does not assign `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`.

## 6. Documents

| File | Role |
| --- | --- |
| `00-EXECUTION-BOUNDARY.md` | This boundary |
| `01-HOST-PROBE.md` | Pod probe |
| `02-SEQUENCE-MATRIX.md` | Required sequence |
| `03-MERGED-DESIGN-EXERCISER.md` | `check-guards.sh` process result |
| `04-MISSING-PREREQUISITES.md` | Exact gaps |
| `05-INDEPENDENT-COUNCIL.md` | Pending council |
| `EXECUTION-MANIFEST.json` | Classification and file hashes |
| `SEQUENCE.json` | Machine-readable rows |
