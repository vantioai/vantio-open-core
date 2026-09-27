# @vantio/optics-otel-i3

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

WS7 I3. This package is a default-disabled OTLP/HTTP JSON traces adapter. It reads the approved WS7-I2 mapping and does not modify it. Metrics and logs are not implemented.

Calling the package does not export. A send happens only when that call passes `enabled: true`, `adapter: "otlp_traces"`, and a customer http(s) endpoint whose path is `/` or `/v1/traces`.

The adapter does not read environment variables, does not load the live CLI or SDKs, and does not accept credential headers. Public docs still say Optics does not export OTLP.

`schema_status` is `unstable-pre-1.0`. `mapping_version` is `0`. There is no schema URL.

Run the isolated tests from the repository root:

```sh
node --test tests/optics-otel-i3/*.test.cjs
node --test tests/optics-otel-mapping/*.test.cjs
```
