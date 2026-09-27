# Merged design exerciser

Audience: INTERNAL_RESTRICTED

Environment class: `CLEAN_HOST_INTERNAL_PROOF`

Evidence tier: `UNSET`

This file records one run of the merged script contract. It does not change any row in `02-SEQUENCE-MATRIX.md`.

## 1. Command

Working tree: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

Command: `docs/planning/clean-host-lifecycle/scripts/check-guards.sh`

Started: `2026-09-27T11:18:58Z`

Exit code: `0`

Stdout:

```
check_guards=PASS
evidence_tier=UNSET
stranger_host=NOT_RUN
phantom_box=EXCLUDED
temporary_lab_removed_on_exit=true
```

`$HOME/.vantio` was `ABSENT` before the command and `ABSENT` after it. `git status --porcelain` was empty after the command. The script's temporary root under `/tmp` is removed by its own exit trap. No run file from that cycle is in git.

## 2. What exit 0 covers

The script, as written in `03-LIFECYCLE-SCRIPT-INVENTORY.md`, clears control-plane variables in its own process, expects the refusal exit codes, resets, captures one loopback fixture, retains it, checks the manifest fields, expires that cycle, resets again, checks the operator data directory, and deletes the temporary root.

Refusal cases exercised by that script include stranger-host (exit `20`), `VANTIO_SOAK_LOCAL=1` (exit `21`), `VANTIO_API_KEY` (exit `21`), `VANTIO_INGEST_URL` containing `:5001` (exit `21`), and `VANTIO_HOME` (exit `22`).

`check_guards=PASS` means those assertions held on this pod. `evidence_tier` stays `UNSET`. `stranger_host` stays `NOT_RUN`. `phantom_box` stays `EXCLUDED`.

## 3. What this run leaves closed

The capture inside the exerciser is the free observe path on `127.0.0.1` defined by the merged design. The shape check requires action `OBSERVED`. The retained bundle is deleted before the script exits. That cycle is not a host observe, ingress, egress, allow, deny, enforcement, export, or residual inspection for the required sequence.

The design's earlier scaffold record on commit `319c74e064a394bb2e64999c723b028d52b4574a` is a different run. This section is the `2026-09-27T11:18:58Z` run on `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.
