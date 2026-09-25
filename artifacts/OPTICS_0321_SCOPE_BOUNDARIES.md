# Optics 0.3.21 scope boundaries

**Date:** 2026-09-25  
**Founder council:** `PROCEED_COPY_FIX_ONLY`  
**Package:** `@vantio/cli` 0.3.21  
**Status:** internal record. This file is not part of the npm package.

## Control-plane client

The control-plane client in `packages/vantio-cli/bin/interceptor.cjs` is out of scope for Optics 0.3.21.

It is not reachable in ordinary local use. It fires only when the caller supplies both `VANTIO_INGEST_URL` and `VANTIO_API_KEY` aimed at a caller-chosen host. On `vantio.ai` and `www.vantio.ai`, a key is ignored and this client does not run.

It is not documented as an Optics 0.3.21 service. It is reserved for a separately scoped future product.

## Hidden logout

`vantio logout` is retained as a hidden local-only command in 0.3.21. Its purpose is to give 0.3.20 upgraders a sanctioned path to delete `~/.vantio/config.json`. It does not read the file, print it, or use the network.

Rename or removal is deferred to a later release. This record does not schedule that release.

## Account and cloud sync

No account or cloud-sync product is scheduled by Optics 0.3.21.

## Release authority

This record does not authorize merge of PR #45, npm publication, a tag, a GitHub release, a production endpoint change, credential issuance, a Phantom Engine change, or a pricing change.
