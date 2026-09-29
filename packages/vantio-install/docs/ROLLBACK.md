# Rollback

Rollback reverses the product changes recorded for that transaction. It stops the Phantom Engine container this transaction started, unloads the `vantio-pe-observe` AppArmor profile this transaction loaded, removes the image and staged archive this transaction loaded, and removes the receipts this transaction wrote.

A customer rollback uses both live gates and the plan hash. `--fixture-host` is forbidden for customer operators. A rollback that omits either live gate is ungated and is not a customer operation. Raw `docker` outside the installer argv list is forbidden. Privilege symptoms are in `PREFLIGHT.md`.

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install rollback --transaction-id <id> --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`

The command is bound to that transaction. It does not accept a different plan hash, and it does not enable enforcement.

The plan's `live_operations` list must match this installer. That comparison runs before the tracefs fact is read. A list that is present but different, including a plan written before the `vantio-pe-observe` load and unload operations, is refused. The refusal names that mismatch. Roll that plan back with the installer that wrote it. An empty or absent list is still reported as a missing live operation list. This installer does not rewrite an older plan into the current list.

A saved host snapshot with no `tracefs_mounted` key can still roll back when the operation list matches. The parent installer did not record that fact. Rollback does not treat the missing key as an absent mount and does not re-probe tracefs. Apply of that same plan re-probes the live host.

When rollback finishes, `state` is `ROLLED_BACK`. Run `vantio-install verify-removal --transaction-id <id> --json` next. Removal is confirmed when that command reports `VERIFIED_REMOVED`.

If the Optics CLI is on disk at `<prefix>/bin/vantio` but that install step was not checkpointed, rollback still removes `bin/vantio` and the `@vantio/cli` package directory under the prefix. `verify-removal` reads that prefix from disk. It does not report `VERIFIED_REMOVED` while `bin/vantio` remains, including when the saved host snapshot has no CLI version.

If an Agent SDK tree or `agent-sdk-receipt.json` is on disk under the prefix and `install_agent_sdks` was not checkpointed, rollback still removes `lib/node_modules/@vantio/agent-sdk`, the `vantio` module, the `vantio_agent_sdk` dist-info under the prefix, and the receipt. `verify-removal` reads those paths from disk. It does not report `VERIFIED_REMOVED` while any of them remain, including when the saved host snapshot has no SDK version.

After the container stops, rollback unlinks these pinned map names under `/sys/fs/bpf`: `vantio_trace_map`, `vantio_enrolled_cgroups`, `vantio_debug_counters`, `vantio_debug_last_comm`, and `vantio_tls_severed_pids`. The unlink removes that directory entry. It does not follow a symlink, and it leaves every other name in the directory alone. `verify-removal` with `--scope pe` or `--scope all` reads those names from `/sys/fs/bpf`. An empty pin list in the saved host snapshot does not hide a name that is still there. `VERIFIED_REMOVED` is reported only when the residual list is empty. When that directory cannot be read, the result is `UNKNOWN` and the state is `FAILED_SAFE`.

When `verify-removal` reports `RESIDUAL_FOUND` (live) or `RESIDUAL_PRESENT` (fixture) because `<prefix>/bin/vantio`, an Agent SDK tree, or one of those pin names is still present, run the same dual-gated rollback again. That recovery removes the prefix artifacts and unlinks the pin names, including when the container stop was already recorded. `uninstall --scope pe` or `--scope all` with the same gates unlinks the pin names too. `--scope optics` leaves them in place. Run `verify-removal` again afterward. `VERIFIED_REMOVED` is reported only when the residual list is empty. Apply stays refused from either residual state.

If the process stops in the middle, `status` reports `INTERRUPTED`. Run rollback again with the same transaction id to continue from the saved checkpoint.
