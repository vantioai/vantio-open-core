# Uninstall

`vantio-install uninstall --transaction-id <id> --scope all --yes --json` removes the product files recorded for that transaction. `--scope pe` removes Phantom Engine and leaves Optics in place. `--scope optics` removes the Optics CLI, the Agent SDK package trees, and the receipts under the prefix. `--scope all` removes both.

A live uninstall uses the same two gates and the same plan hash as apply. `state` becomes `UNINSTALLED` when the commands finish. Run `verify-removal` with the same scope. `VERIFIED_REMOVED` means the residual list for that scope is empty. `RESIDUAL_PRESENT` means something from that scope is still on the host, and the JSON lists it. A live check uses `RESIDUAL_FOUND` for that same situation and exits 2. `verify-removal` does not take the live mutation flag.

`RESIDUAL_FOUND` and `RESIDUAL_PRESENT` can start another uninstall. `--scope optics` or `--scope all`, with the same two gates, removes the Optics CLI, the Agent SDK trees, and the receipts under the prefix. `--scope pe` leaves that prefix in place, and a later `verify-removal` still reports the residual while those files are on disk. Run `verify-removal` again after the optics or all scope finishes.

Evidence for the transaction stays on disk so you can still read what happened.
