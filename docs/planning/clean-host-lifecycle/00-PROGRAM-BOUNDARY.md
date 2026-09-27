# Clean-host lifecycle lab — program boundary

Audience: INTERNAL_RESTRICTED

Producer role: planning producer only. This agent does not sit the independent council, does not self-assign a council pass, and does not assign an evidence tier.

Producer identity: Cursor cloud agent `bc-696d1176-5194-564e-a77c-9001563d5885`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-696d1176-5194-564e-a77c-9001563d5885

Producer classification: `CLEAN_HOST_LAB_DESIGN_READY_FOR_COUNCIL`

That classification means this design packet is ready for a separate council. It is not a council verdict. It is not `STRANGER_HOST_PROVED`. It is not `PROVED_EXTERNAL`. It is not `CUSTOMER_VALIDATED`.

Environment class: `CLEAN_HOST_INTERNAL_PROOF`

`INTERNAL_PROOF` is the lab's requirement-status label. In `docs/internal/optics-best-in-class-roadmap.md` that label is a requirement status, and it is not an evidence tier. This packet does not write it into `docs/architecture/optics-foundation/TRACEABILITY-MATRIX.json`. Displaying it as customer validation is outside this design.

## 1. Locked input

| Item | Value verified at planning time |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `5064f32f1cdfcb840dfd100e2ce5c712d046550d` |
| Commit subject | Merge pull request #65 from `vantioai/docs/documentation-release-governance-v1` |
| `origin/main` | Same commit. Fetched before this branch was written. The VM snapshot was at `587f3b94d47ea958f91d3a99125cd55931d995f1` until that fetch. |
| Branch | `cursor/clean-host-lifecycle-lab-5885` |
| Writable path | `docs/planning/clean-host-lifecycle/` |
| CLI | `@vantio/cli` `0.3.24` in `packages/vantio-cli/package.json` |
| Schema | `schema_status` `unstable-pre-1.0` on lab manifests |
| Evidence tier | `UNSET` |
| Stranger-host | `NOT_RUN` |
| Phantom-Box | `EXCLUDED` |

## 2. What this force does

- Defines an internal clean-host lab that is independent of Phantom-Box.
- Specifies reset, capture, retention, expiry, and stop behavior for that lab.
- Adds lifecycle scripts under `scripts/` that enforce those rules on a disposable `HOME`.
- Leaves `06-INDEPENDENT-COUNCIL.md` as `PENDING_INDEPENDENT_COUNCIL`.

The scripts are in-repo artifacts. A zero exit code from a script is a process result. It is not an evidence tier.

## 3. What this force keeps closed

- Product code, package versions, workflows, tags, GitHub releases, npm, and PyPI.
- Phantom Engine, the Phantom-Box soak flag, and the local control plane on port `5001`.
- Stranger-host execution, external proof, and customer validation.
- Evidence-tier assignment, including any edit to the traceability matrix.
- Public manuals, governance inventories, and announcements.
- SQLite, retention inside the product, a daemon, OTLP, and alerting.
- Python capture. The published Python package is not invoked. Unpublished Python source is not the product.

## 4. Classification rules

| Field | Value this packet is allowed to write |
| --- | --- |
| `environment_class` | `CLEAN_HOST_INTERNAL_PROOF` |
| `evidence_tier` | `UNSET` |
| `stranger_host` | `NOT_RUN` |
| `phantom_box` | `EXCLUDED` |
| `customer_validation` | `UNSET` |
| `independent_verifier` | `UNSET` |
| `requirement_status_label` | `INTERNAL_PROOF` |

A later council may accept or reject the design. Acceptance of the design still leaves the evidence tier unset. A later force that wants `STRANGER_HOST_PROVED` needs a different host and a different charter. This lab is not that charter.

## 5. Scaffold self-check

Status: `RECORDED`

Command: `docs/planning/clean-host-lifecycle/scripts/check-guards.sh`

Ran on commit: `319c74e064a394bb2e64999c723b028d52b4574a`

That commit is the packet before this record was added. The script bytes exercised there are the bytes in that commit. This section is the record. It is not a new run.

Exit code: `0`

Stdout:

```
check_guards=PASS
evidence_tier=UNSET
stranger_host=NOT_RUN
phantom_box=EXCLUDED
temporary_lab_removed_on_exit=true
```

The script created a temporary lab root under `/tmp`, ran the refusal cases, reset, captured one loopback fixture, retained it, expired it, and deleted the temporary root on exit. The operator data directory snapshot was unchanged. Nothing from that cycle is in git.

`check_guards=PASS` means those assertions held. It does not assign an evidence tier. `evidence_tier` stays `UNSET`. `stranger_host` stays `NOT_RUN`. `phantom_box` stays `EXCLUDED`.

`node docs/scripts/check-docs-release.mjs` also exited 0 on this producer VM after that run. That check is the documentation governance gate. It is not an evidence tier for this lab.

## 6. Documents

| File | Role |
| --- | --- |
| `00-PROGRAM-BOUNDARY.md` | This boundary |
| `01-ARCHITECTURE.md` | Lab architecture |
| `02-RESET-AUTOMATION-PLAN.md` | Reset plan |
| `03-LIFECYCLE-SCRIPT-INVENTORY.md` | Script inventory |
| `04-STOP-CONDITIONS.md` | Stop conditions |
| `05-EVIDENCE-RETENTION.md` | Evidence retention |
| `06-INDEPENDENT-COUNCIL.md` | Pending council |
| `LAB-MANIFEST.json` | File hashes and classification |
| `scripts/` | Guarded lifecycle scripts |
