# T5 lab integration step

Audience: INTERNAL_RESTRICTED

Date: 2026-10-16

Status: `NOT_WIRED`

The drill catalog is `scripts/clean-host/t5/catalog.json`. The registration file is `scripts/clean-host/t5/LAB-REGISTRATION.json`. `cloud_run` is false.

This track does not run a cloud lab and does not edit a lab workflow. Lab agent `bc-8b310b16` owns the lab slot. `6d3ce580` is not the working seal. The public pin stays `e0b19d55`.

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
