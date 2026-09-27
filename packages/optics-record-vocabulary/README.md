# @vantio/optics-record-vocabulary

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

PKG-02 Unit A only. This package is a private vocabulary, conformance fixtures, and structural checks. It does not write run logs, read live run directories, migrate records, or import the live CLI, Python SDK, or Node SDK.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. JSON Schema is not the source of truth.

Run the isolated tests from the repository root:

```sh
node --test tests/optics-record-vocabulary/*.test.cjs
```
