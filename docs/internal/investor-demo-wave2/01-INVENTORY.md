# Inventory

Audience: INTERNAL_RESTRICTED

Read before implementation. Versions below were taken from this tree at `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.

## Design

`43cc35371e109e6a377cc31e4fd2438bfceea797` is commit `43cc353` ("Revise the investor demo design after council needs-revision"). Pull request #75 merged it. The files under `docs/programs/production-readiness/demo/` still say the design producer classification `INVESTOR_DEMO_DESIGN_REVISION_READY_FOR_COUNCIL` and `wave2: NOT_AUTHORIZED`. This force treats that merged tip as the design to implement. It does not rewrite those files and does not convert their classification into a council pass.

`founder_text` is `ABSENT` on B01–B18. This force keeps that sequence. The show list in the Wave 2 brief is the card set, not a replacement for the beats.

`10-WAVE2-SCAFFOLD.md` requires a labeled demo writer, simulation labels on prove and discover totals, a fixed-id flag, a sentinel-scoped reset, and an F1 stop. It also says the labeled writer is a future CLI version, not a silent edit of 0.3.24. The standing order for this force says not to reopen CLI 0.3.24. The runner is that writer, outside the frozen package.

## CLI

`packages/vantio-cli/package.json` version is `0.3.24`. `demoCommand` writes hostname `optics-demo.invalid`, action `OBSERVED`, bytes 0, and no `evidence_origin`. `discover` prints an observed-locally count that includes that host. `prove --format=md` does not print `SIMULATED_DEMO`. Readers use `os.homedir()`, so `HOME` isolates them. Default `status` does not contact a registry.

## Other sources used by cards

| Card | Source in this tree | What the tree actually contains |
| --- | --- | --- |
| Coverage | `docs/products/optics/SUPPORTED-PATHS.md` | Unobserved paths are not blocked. This room does not start an agent. |
| Descendant authority | `docs/planning/enterprise-governance/02-E2-DELEGATED-AUTHORITY.md` | Planned records. No live grant store. `ACTIVE` requires a host report. |
| Health | `docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json` | Catalog values include `degraded`, `observing`, and `not_enrolled`. |
| Optics observation | CLI `demo` | In-process stub. No network. |

Phantom Engine is not in this repository. Enforcement, host enrollment, and cluster behavior are not executed.
