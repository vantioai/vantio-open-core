# PKG-02 Unit A aliases

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Alias ownership is built only from canonical rows. A compatibility row documents a live name. It does not add a second owner.

## Graph rules

- An alias edge points from the legacy key to one canonical name.
- Fan-out per field is at most 8. The vocabulary uses 19 edges. The widest field has 2.
- Walk depth is capped at 4. The real edges are one hop.
- A self-alias is a cycle.
- One alias maps to one canonical name across record types. `trace_id` maps to `run_id` on both `run_envelope` and `observation_event`. That is one owner name, not two.
- When the alias string is also a different canonical field, the row records `collides_with_different_canonical_field`.

## The trace_id collision

Live envelope `trace_id` is the run boundary. The canonical field `trace_id` is validated trace context. The alias therefore belongs to `run_id`.

The inherited-trace fixture stores `run_id` and `trace_id_basis` `ASSERTED_CONTEXT`. It does not store the live string in canonical `trace_id`. The witnessed-trace fixture is the only declared case of `OPTICS_GENERATED`, and only when the input carries `PKG01_OPTICS_GENERATED_WITNESS`. The witness is not copied onto the canonical record.

## Other read aliases

| Alias | Canonical field |
| --- | --- |
| `pid`, `ppid` | `process_id`, `parent_process_id` |
| `node_version` | `runtime_version` |
| `cli_version`, `producer_version` | `cli_or_sdk_version` |
| `ts` | `started_at` |
| `generated_at` | `ended_at` |
| `summary.total_calls` | `call_count` |
| `hostname`, `host` | `destination_host` |
| `provider` | `provider_id` |
| `status`, `httpStatus` | `http_status` |
| `applicationStatus` | `application_status` |
| `opticsStatus` | `optics_status` |
| `bytes` | `response_bytes` |

`generated_at` remains a read alias of `ended_at`. The CLI fixture does not store write time as `ended_at`.

`applicationStatus` does not write `optics_status`. `opticsStatus` `SUCCESS` on a Python 3.1.0 call is refused as canonical optics health.

Prohibited live names (`plane`, `cost`, `machine`, and the rest of the PKG-01 prohibited list) are compatibility rows with dimension `prohibited_legacy`. They are not canonical aliases.

No alias is removed. Removal waits for a later versioned release and a reader matrix. This unit does not perform that removal.
