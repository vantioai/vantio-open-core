# WS7 I2 implementation report

PRIVATE | INERT | NOT SHIPPED | ADAPTERS DISABLED | NO OTLP EXPORTER | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Revision classification: `OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL`

The failed tip `dd9359e7c374d21986b3c7ec57d69946328d2252` carried `OTEL_MAPPING_DESIGN_READY_FOR_COUNCIL`. Council returned `OTEL_MAPPING_DESIGN_NEEDS_REVISION`. This report records the revision. It is not a council verdict, not a merge, and not a statement that an exporter exists.

The revising agent did not sit the council. Adapters stay disabled. I3 stays `NOT_AUTHORIZED`.

## Revision

- Canonical preview candidates are considered only when `evidence_origin` is `LOCAL_OBSERVATION`. `PRODUCT_HEALTH` and `DERIVED_DIAGNOSTIC` yield an empty candidate set. `PRODUCT_HEALTH` does not set client span status `OK`. `SIMULATED_DEMO`, `TEST_FIXTURE`, `IMPORTED`, and a missing origin stay empty.
- `http.request.method`, `http.response.status_code`, `url.path`, and `url.scheme` are cited from semantic-conventions `v1.37.0` `docs/registry/attributes/http.md`, `docs/registry/attributes/url.md`, and `docs/http/http-spans.md`. They are not cited from `docs/gen-ai/gen-ai-spans.md`. `url.path` is on the HTTP server span table. The public sketch is unchanged and still says Optics does not export OTLP.
- The mapping tests no longer contain retired product-name literals. They scan this package, its tests, and these internal notes with the documentation-release stale-name patterns.

## What landed

Private package `@vantio/optics-otel-mapping` at `0.0.0-unstable-pre-1.0`. It is not a bump of CLI `0.3.24`, Node SDK `0.2.4`, Python `3.1.0`, `@vantio/optics-evidence-contract`, or `@vantio/optics-record-vocabulary`.

The package is not in `pnpm-workspace.yaml`. It has no dependencies.

The mapping document is version `0`, id `WS7-I2`, `schema_status` `unstable-pre-1.0`, `schema_url` null. `public_shipped_support` is false. Founder decision 12 stays unresolved.

Three adapters are declared: `otlp_traces`, `otlp_metrics`, `otlp_logs`. Each is `default_enabled` false and `implementation` `NOT_PRESENT`.

`docs/optics-otel-mapping.md` is unchanged.

## Checks

From the repository root:

```sh
node --test tests/optics-otel-mapping/*.test.cjs
```

The producer run of that command reported 22 tests and 0 failures. The revision run reported 24 tests and 0 failures. The added tests cover `PRODUCT_HEALTH`, `DERIVED_DIAGNOSTIC`, `TEST_FIXTURE`, and `IMPORTED` empty candidate sets, and the HTTP and URL citations. `node docs/scripts/check-docs-release.mjs` reported ok on the revision, including `legacy-stale-name-inventory-frozen`.

## Hard-stop attestations

- No CLI, Python SDK, or Node SDK source change.
- No evidence-contract or record-vocabulary change.
- No public sketch change and no shipped-support sentence.
- No OTLP client and no network export.
- Adapters default to disabled, and this package has no enable path.
- No stable schema and no schema URL.
- No release, seal, publish, tag, or announcement.
- I3 is not authorized.
- Council is a separate agent. This producer did not run it.
