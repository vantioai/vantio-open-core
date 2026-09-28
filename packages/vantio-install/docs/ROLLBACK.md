# Rollback

`vantio-install rollback --transaction-id <id> --yes --json` reverses the product changes recorded for that transaction. It stops the Phantom Engine container this transaction started, removes the image and staged archive this transaction loaded, and removes the receipts this transaction wrote.

When rollback finishes, `state` is `ROLLED_BACK`. Run `vantio-install verify-removal --transaction-id <id> --json` next. Removal is confirmed when that command reports `VERIFIED_REMOVED`.

If the process stops in the middle, `status` reports `INTERRUPTED`. Run rollback again with the same transaction id to continue from the saved checkpoint.
