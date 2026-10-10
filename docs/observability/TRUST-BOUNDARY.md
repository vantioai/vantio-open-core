# Export trust boundary

`product_otlp_export_authorized` is false. Observability integration is NOT_PROVEN.

## What the current bind does

`attestSourceRecord` and `attestObservation` copy one object's own fields and remember that object in this process. Export sends that copy. A different object is marked `unattested` and is not sent. If the original object's data changes after the copy, the reason is `ATTESTATION_MISMATCH` and nothing is sent.

The first `startFromConfig` call holds the in-process send token. A later `startFromConfig` call cannot send.

The OTLP attribute `vantio.attestation` is the label `in-process`. A receiver cannot use it as proof.

## The boundary that would close the residual

The boundary that would close this is a source identity signed outside the observed process, checked before send. The signer is Phantom Engine, or the Enterprise evidence signer, over the canonical event bytes. The exporter rejects an event whose signature does not verify. A co-resident caller does not hold that key, so it cannot mint the signature. The in-process token is not that key.

`canonicalEventBytes` and `checkBeforeSend` are that check. `checkBeforeSend` runs before a batch is sent when `externalTrust.publicKey` is set. A missing or invalid signature is not sent. `trust.authorized: true` is refused. `PRODUCT_OTLP_EXPORT_AUTHORIZED` stays false, and the OTLP label stays `in-process`, including after a signature verifies. The public key has to be the Phantom Engine or Enterprise signer key, supplied from outside this process. A key generated beside the exporter does not close the residual, because the same process can read a private key that lives with it.

No production signing root is used here.

A valid base64 value is checked before a host name is lowercased. Lowercasing first hid a mixed-case base64 canary from the decoder. A string that was already case-folded in the base64 alphabet does not decode back to the original text, so it is not that canary.

## Known residual

A co-resident caller of `attestSourceRecord`, `attestObservation`, or `createExporter` can bind an object it built and send it. That caller is inside the process. The bind does not keep it out.

This residual is not a pass. It stays open until a signer outside the process is actually verified on the export path. `product_otlp_export_authorized` stays false.

## Why that check did not land this cycle

The check needs a signature over the canonical event bytes from a key the observed process does not hold. Two lanes were asked for that signer.

- Cloud agents `bc-2b9fb1af` (Phantom Engine) and `bc-3ae82b99` (Enterprise evidence) were not readable from this run.
- Phantom Engine `main` at `7d3e53fae34008728631f5609e80d4506b6e9e8f` is host enforcement. It does not sign an observability event.
- Enterprise `cursor/optics-evidence-export-5bed` at `a5b40a4f19722e6c55caca3b5f87af9f50c5cc00` seals an observation fragment. The seal can carry a test signature. The private key is supplied by the caller, the key id must be a non-production test id, and a production root is refused. That seal is not an out-of-process identity for the OTLP export, and a caller who can reach the test key can sign an object they built.

No production signing root is used. A test key next to the exporter would not close the residual. The export path still does not verify an outside signature before send.
