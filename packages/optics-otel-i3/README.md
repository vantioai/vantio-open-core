# @vantio/optics-otel-i3

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

WS7 I3. This package is a default-disabled OTLP/HTTP JSON traces adapter. It reads the approved WS7-I2 mapping and does not modify it. Metrics and logs are not implemented.

Calling the package does not export. A send happens only when that call passes `enabled: true`, `adapter: "otlp_traces"`, and a customer http(s) endpoint whose path is `/` or `/v1/traces`.

A caller-built `canonical_observation` is not sent. `attestSourceRecord` copies the object's own data once and export uses that copy. A different object, a field named `signature`, or any unbound object is marked `unattested` and is not sent. If the original object's data changes after the copy, export marks `ATTESTATION_MISMATCH` and does not send. Calling `attestSourceRecord` is the source act: a co-resident caller of that function can bind its own object. That is not a separate identity, not a Phantom Engine signature, and `product_otlp_export_authorized` stays false.

The adapter does not read environment variables, does not load the live CLI or SDKs, and does not accept credential headers. Public docs still say Optics does not export OTLP.

`schema_status` is `unstable-pre-1.0`. `mapping_version` is `0`. There is no schema URL.

Run the isolated tests from the repository root:

```sh
node --test tests/optics-otel-i3/*.test.cjs
node --test tests/optics-otel-mapping/*.test.cjs
```
