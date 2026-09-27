# Scaffolding

Audience: INTERNAL_RESTRICTED

`labeled-event-envelope.json` is a design object for the simulation-label rule.

- `implementation_status` is `NOT_AUTHORIZED`.
- `simulation_label` is `SIMULATED_DEMO`.
- It has no `vantio_run_log` field, so CLI 0.3.24 run readers that require that marker will not treat it as a run log.
- Do not copy it into `~/.vantio/runs/`.
- Wave 2 may persist the same fields from a future demo writer. This directory does not authorize that writer.
