# T5 lab integration step

Audience: INTERNAL_RESTRICTED

Date: 2026-10-16

Status: `WIRED_NOT_DISPATCHED`

The drill catalog is `scripts/clean-host/t5/catalog.json`. The registration file is `scripts/clean-host/t5/LAB-REGISTRATION.json`. `cloud_run` is false.

Lane K wires battery id `t5-egress` and does not start a guest. The lane lab seal is `6d3ce580`. The public pin stays `e0b19d55`. Lab agent `bc-8b310b16` owns the AWS slot through Monday. This change does not start an AWS workflow.

GCP project `vantio-lab-oct08` is the only project the plan accepts. At `2026-10-16T21:47:32Z` there was no in-progress Actions run. The plan in `scripts/gcp/t5_lab_plan.py` returns `dispatch: false` because the keyless workflow on main has no t5 input. Workflow permissions were not edited.

## What a later lab agent does

1. Read `scripts/clean-host/t5/LAB-REGISTRATION.json`.
2. Copy `scripts/clean-host/t5` and `packages/t5-egress-drills` onto a guest that agent already owns.
3. Add battery id `t5-egress` to the allow-list in `scripts/aws/w3_lab_steps.py` in a separate change. Until that change, an unknown battery id is rejected.
4. Run `python3 scripts/clean-host/t5/proof.py` on that guest. The proof uses `unshare` and does not need a routed interface.
5. Keep the result labeled Lab-only. A guest run is still not a cluster attach and not a customer result.

## What this track already ran

`python3 scripts/clean-host/t5/proof.py` on the cloud-agent runner. The evidence file is `docs/planning/gap-t5-egress/evidence/proof.json`. Label: Lab-only.

Files this track did not change:

- `.github/workflows/w3-lab-*.yml`
- `.github/workflows/gcp-lab-*.yml`
- `scripts/aws/w3_lab_steps.py`
- `README.md`
- installer pin files
