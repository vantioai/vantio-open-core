# Uninstall

Uninstall removes the product files recorded for that transaction. `--scope pe` removes Phantom Engine and leaves Optics in place. `--scope optics` removes the Optics CLI, the Agent SDK package trees, and the receipts under the prefix. `--scope all` removes both.

A customer uninstall uses both live gates and the same plan hash as apply. `--fixture-host` is forbidden for customer operators. An uninstall that omits either live gate is ungated and is not a customer operation. Raw `docker` outside the installer argv list is forbidden.

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install uninstall --transaction-id <id> --scope all --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`

`state` becomes `UNINSTALLED` when the commands finish. Run `verify-removal` with the same scope. `VERIFIED_REMOVED` means the residual list for that scope is empty. `RESIDUAL_PRESENT` means something from that scope is still on the host, and the JSON lists it. A live check uses `RESIDUAL_FOUND` for that same situation and exits 2. `verify-removal` does not take the live mutation flag.

`RESIDUAL_FOUND` and `RESIDUAL_PRESENT` can start another uninstall. `--scope optics` or `--scope all`, with the same two gates, removes the Optics CLI, the Agent SDK trees, and the receipts under the prefix. `--scope pe` leaves that prefix in place, and a later `verify-removal` still reports the residual while those files are on disk. Run `verify-removal` again after the optics or all scope finishes.

`--scope pe` and `--scope all` also unlink `vantio_trace_map`, `vantio_enrolled_cgroups`, `vantio_debug_counters`, `vantio_debug_last_comm`, and `vantio_tls_severed_pids` under `/sys/fs/bpf` after the container stops. `--scope optics` leaves those names in place. `verify-removal` for `pe` or `all` reads the directory. It reports `VERIFIED_REMOVED` only when the residual list is empty. An empty pin list in the saved snapshot does not hide a name that is still there. When the directory cannot be read, the result is `UNKNOWN` and the state is `FAILED_SAFE`. A name that could not be unlinked stays in the residual list.

Evidence for the transaction stays on disk so you can still read what happened.
