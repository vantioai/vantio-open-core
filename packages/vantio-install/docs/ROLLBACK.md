# Rollback

`vantio-install rollback --transaction-id <id> --yes --json` reverses the product changes recorded for that transaction. It stops the Phantom Engine container this transaction started, unloads the `vantio-pe-observe` AppArmor profile this transaction loaded, removes the image and staged archive this transaction loaded, and removes the receipts this transaction wrote.

A live rollback uses the same two gates as apply, and the same plan hash:

`VANTIO_INSTALL_ALLOW_LIVE=1 vantio-install rollback --transaction-id <id> --yes --plan <PLAN.json> --plan-sha256 <hex> --i-accept-live-mutations --json`

The command is bound to that transaction. It does not accept a different plan hash, and it does not enable enforcement.

When rollback finishes, `state` is `ROLLED_BACK`. Run `vantio-install verify-removal --transaction-id <id> --json` next. Removal is confirmed when that command reports `VERIFIED_REMOVED`.

If the Optics CLI is on disk at `<prefix>/bin/vantio` but that install step was not checkpointed, rollback still removes `bin/vantio` and the `@vantio/cli` package directory under the prefix. `verify-removal` reads that prefix from disk. It does not report `VERIFIED_REMOVED` while `bin/vantio` remains, including when the saved host snapshot has no CLI version.

If an Agent SDK tree or `agent-sdk-receipt.json` is on disk under the prefix and `install_agent_sdks` was not checkpointed, rollback still removes `lib/node_modules/@vantio/agent-sdk`, the `vantio` module, the `vantio_agent_sdk` dist-info under the prefix, and the receipt. `verify-removal` reads those paths from disk. It does not report `VERIFIED_REMOVED` while any of them remain, including when the saved host snapshot has no SDK version.

When `verify-removal` reports `RESIDUAL_FOUND` (live) or `RESIDUAL_PRESENT` (fixture) because `<prefix>/bin/vantio` or an Agent SDK tree is still on disk, run the same dual-gated rollback again. That recovery removes those prefix artifacts. Run `verify-removal` again afterward. `VERIFIED_REMOVED` is reported only when the residual list is empty. Apply stays refused from either residual state.

If the process stops in the middle, `status` reports `INTERRUPTED`. Run rollback again with the same transaction id to continue from the saved checkpoint.
