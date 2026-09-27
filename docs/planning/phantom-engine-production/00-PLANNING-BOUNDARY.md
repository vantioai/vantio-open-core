# Phantom Engine wave 1 — packaging and health planning boundary

Audience: INTERNAL_RESTRICTED

Producer role: planning producer only. This agent does not sit the independent council, does not self-assign a council pass, and does not authorize a build, a publish, a load, or a deploy.

Producer identity: Cursor cloud agent `bc-67390466-de62-5277-ba0b-3f01b390aa8c`, model Grok 4.7.

Producer classification: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

That classification means the planning packet is ready for a separate council. It is not a council verdict, not an implementation authorization, and not evidence that any package, image, or host was proved in this force.

## 1. Locked input

| Item | Value verified at planning time |
| --- | --- |
| Writable repository | `vantioai/vantio-open-core` |
| Open-core base | `5064f32f1cdfcb840dfd100e2ce5c712d046550d` |
| Base subject | Merge pull request #65 from `vantioai/docs/documentation-release-governance-v1` |
| Planning branch | `cursor/phantom-wave1-packaging-health-aa8c` |
| Writable path | `docs/planning/phantom-engine-production/` only |
| Founder force | WS3 wave 1, Phantom packaging and health/coverage design |
| Private product repo read | `vantioai/vantio-phantom-engine` tip `631e435315cd780d83d3259e111893c1d0569bc3` (2026-09-20) |
| Enterprise repo tip read | `vantioai/vantio-enterprise` `2df2d1f2d2e5a8e65c6d3021b20b94f179e485b7` (2026-08-23, branch `master`) |
| Customer-docs repo | `vantioai/vantio-pe-customer-docs` returned an empty repository (HTTP 409 on `heads/main`) |
| Workstream 4 vocabulary | `DEFINITION_NOT_RETRIEVED` |

Program item names in this packet are the founder-force parentheticals:

| ID | Subject |
| --- | --- |
| P1 | Package and artifact provenance |
| P2 | Prerequisite and compatibility |
| P24 | Health and coverage |

These IDs are not the June audit severity labels. The private remediation register uses “P2” for findings F-13 through F-17. The enterprise script `scripts/cloud_platform_readiness.py` titles itself “P1 #12”. Those older numbers stay in their own files. This packet does not renumber them.

## 2. What this force does

- Inventories private Phantom Engine commit constraints that were readable, and records the access gaps that were not.
- Plans P1, P2, and P24 against blobs on tip `631e435315cd780d83d3259e111893c1d0569bc3`.
- Binds P24 to the protection-state and verifier vocabularies already in that tree, and records that Workstream 4 has not published a shared catalog for this force to adopt.
- Leaves `06-INDEPENDENT-COUNCIL.md` as `PENDING_INDEPENDENT_COUNCIL`.

## 3. What this force keeps closed

- Live eBPF load, `bpftool`, kernel verifier runs, and `cargo build` of the Phantom crates.
- `kind`, Docker build, image pull, GHCR inspection, Helm install, and DaemonSet apply.
- Stranger-host execution, customer hosts, and customer deploy.
- npm, PyPI, GHCR publish, tags, and GitHub Releases.
- Edits to `vantio-phantom-engine`, `vantio-enterprise`, and `vantio-pe-customer-docs`.
- Customer-manual bodies. `docs/operations-guide.md` on the private tip is classified `CUSTOMER_SHIPPED`. This packet cites its blob id and distribution class. It does not copy the guide.
- `docs/governance/` and product code in open-core.

`vantio-pe-customer-docs` had no commit to read. Parallel workstream WS9 owns relocation of private customer docs. This packet does not write that repository.

## 4. Evidence rule for every later section

Repository sentences that say a row was verified on WSL2 or on local `kind` are `OBSERVED_FROM_REPOSITORY_EVIDENCE`. This force did not re-execute them. `kind` remains local kubelet/containerd on one host kernel. Managed GKE, EKS, and AKS remain `TARGET_DESIGN` in `docs/product-spec.md` (blob `f12c0caf7413dc061d705c8fc78ce7d2bcdc525d`). A company reference host is not a stranger host.

## 5. Public-repo boundary already on this base

Open-core `docs/governance/PE-CUSTOMER-BUNDLE.json` at `5064f32f1cdfcb840dfd100e2ce5c712d046550d` states that this repository does not contain a Phantom Engine customer manual, that `docs/scripts/fixtures/pe-customer-bundle/PRIVATE-MANUAL.md` is a test double, and that public package file lists must not include `PRIVATE-MANUAL` or `CUSTOMER-MANUAL` paths. This packet adds neither path.
