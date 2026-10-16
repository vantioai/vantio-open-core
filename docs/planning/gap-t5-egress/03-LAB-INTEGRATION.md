# T5 lab integration step

Audience: INTERNAL_RESTRICTED

Date: 2026-10-16

Status: `INPUT_READY_NOT_DISPATCHED`

The drill catalog is `scripts/clean-host/t5/catalog.json`. The registration file is `scripts/clean-host/t5/LAB-REGISTRATION.json`. `cloud_run` is false.

Lane K wires battery id `t5-egress` and does not start a guest. The lane lab seal is `6d3ce580`. The public pin stays `e0b19d55`. Lab agent `bc-8b310b16` owns the AWS slot through Monday. This change does not start an AWS workflow.

GCP project `vantio-lab-oct08` is the only project the plan accepts. The keyless workflow input is `t5_egress`, default false. It does not run the enterprise batteries. Dispatch stays off until a human starts that input on main after this file is the workflow on main. Workflow permissions were not edited.

## What a later lab agent does

1. Read `scripts/clean-host/t5/LAB-REGISTRATION.json`. The battery id is already on the allow-list.
2. Use a guest that agent already owns. Do not start one while `bc-8b310b16` has the AWS slot, and do not dispatch GCP while a battery from that agent is in progress.
3. The guest command is `scripts/aws/lab-guests/t5-egress.sh`. It runs `python3 scripts/clean-host/t5/proof.py` and `python3 scripts/clean-host/t5/kernel_proof.py`. The proof uses `unshare` and does not need a routed interface. The script does not attach.
4. A dispatch still needs the keyless workflow on main to grow an input for this battery. This change does not add that input.
5. Keep the result labeled Lab-only. A guest run is still not a cluster attach and not a customer result.

## What this track already ran

`python3 scripts/clean-host/t5/proof.py` on the cloud-agent runner. The evidence file is `docs/planning/gap-t5-egress/evidence/proof.json`. Label: Lab-only.

`python3 scripts/clean-host/t5/kernel_proof.py` compiled the program and did not load it. The evidence file is `docs/planning/gap-t5-egress/evidence/kernel-compile.json`. Compile label: Lab-only. Attach label: Roadmap.

Files this track did not change:

- `.github/workflows/w3-lab-*.yml`
- `.github/workflows/gcp-lab-*.yml`
- `README.md`
- installer pin files
