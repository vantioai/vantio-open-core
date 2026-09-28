# Uninstall

`vantio-install uninstall --transaction-id <id> --scope all --yes --json` removes the product files recorded for that transaction. `--scope pe` removes Phantom Engine and leaves Optics in place. `--scope optics` removes the Optics receipts. `--scope all` removes both.

`state` becomes `UNINSTALLED` when the commands finish. Run `verify-removal` with the same scope. `VERIFIED_REMOVED` means the residual list for that scope is empty. `RESIDUAL_PRESENT` means something from that scope is still on the host, and the JSON lists it.

Evidence for the transaction stays on disk so you can still read what happened.
