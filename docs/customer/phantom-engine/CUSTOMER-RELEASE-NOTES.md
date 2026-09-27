# Customer release notes — manual version 1

**Classification:** CUSTOMER_CONFIDENTIAL  
**Product:** Vantio Phantom Engine  
**Manual version:** 1  
**Product version:** 0.1.0 (loader and image tag); Helm chart 0.1.1  
**Audience:** authorized customers  
**Distribution:** authorized-customers-only  
**Status:** draft  

This file is part of the private Phantom Engine customer manual. It is not a public Optics document, not an npm or PyPI artifact, and not website or `llms.txt` content.

## This draft

Manual version 1 is the first customer operating set for Phantom Engine. It is a **draft** matched to private product commit `631e435315cd780d83d3259e111893c1d0569bc3` (2026-09-20). The open-core branch that holds the draft is based on `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`.

| Pin | Value |
|---|---|
| Loader | 0.1.0 |
| Image | `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` |
| Helm chart | 0.1.1 |
| `appVersion` | 0.1.0 |
| Manual status | draft |
| Customer validation | none recorded |

No image publish, package publish, or cluster deploy was performed to write these notes.

## What customers can operate from this manual

- Host prerequisites and a Helm install that stays in audit mode.
- Bare-metal build of `vantio-loader` from the private repository.
- Enrollment by annotation `vantio.ai/enroll: "true"` or by an explicit cgroup command.
- The difference between audit, scoped enforcement, and node-wide drop.
- Exact allowlists, and the existence of CIDR allow and hard-block flags on the loader.
- Where evidence lives, and the requirement to keep a log copy because the chart scratch volume is ephemeral.
- Clean removal, return to audit, and preservation of logs.

The bundled on-prem Enforce component is required for a complete node and is delivered with the authorized pack. This manual states its health URL and does not replace that pack.

## What this draft does not release

| Item | Status in this draft |
|---|---|
| Managed cloud validation (GKE, EKS, AKS) | **not tested** |
| Live Spanner insert | **not tested** |
| Stranger-host or customer acceptance | **not tested** / **customer validated**: none |
| Standing reconciliation service | **unavailable** |
| Inbound deny, quarantine execution, Signal Share send | **unavailable** |
| A public document, package, or website page | Out of scope. Distribution is authorized-customers-only. |
| A certification or a WORM attestation | Not claimed. |

Lab evidence cited in [EVIDENCE-AND-ASSURANCE.md](./EVIDENCE-AND-ASSURANCE.md) remains **independently tested** on Vantio's lab host and a local `kind` cluster. Citing it in these notes does not move it to **customer validated**.

## Product behavior

Writing this manual did not change the loader, the chart, the image, Optics packages, or any running system. Operators change behavior only when they deploy from the private product repository using [DEPLOYMENT-GUIDE.md](./DEPLOYMENT-GUIDE.md).

## Next review

This draft stops for separate review. It is not an approval to merge onto the public default branch, to publish packages, or to tell a customer that their cluster has been validated.
