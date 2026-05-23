import type { CryptographicAnomalyRecord } from "./types.js";

// ── Spanner mutation shape ────────────────────────────────────────────────────
// Mirrors the raw object accepted by @google-cloud/spanner's
// Transaction.insert() / Transaction.upsert() and the Mutation proto, without
// importing the SDK itself. When the SDK is added, this type is structurally
// compatible with `spanner.table(TABLE).insert(rows)`.

/**
 * Column-ordered insert mutation for a single `CryptographicAnomalyRecords`
 * row. Shape is structurally compatible with the @google-cloud/spanner SDK's
 * `Table.insert()` row object and the Spanner Mutation proto.
 */
export interface SpannerInsertMutation {
  readonly table: typeof TABLE;
  readonly columns: typeof COLUMNS;
  readonly values: ReadonlyArray<readonly [
    TraceId: string,
    EventPayload: string | null,
    AuditMode: boolean,
    CommitTimestamp: CryptographicAnomalyRecord["CommitTimestamp"],
  ]>;
}

const TABLE = "CryptographicAnomalyRecords" as const;

// Column order must stay in sync with schema.ddl PRIMARY KEY declaration and
// the CryptographicAnomalyRecord interface. Changing this order is a
// breaking change — bump the package minor version if columns are added.
const COLUMNS = [
  "TraceId",
  "EventPayload",
  "AuditMode",
  "CommitTimestamp",
] as const;

/**
 * Produces a deterministic, column-ordered Spanner insert mutation object for
 * a single `CryptographicAnomalyRecords` row.
 *
 * The returned object is immutable and free of any SDK dependency — it can be
 * accumulated into a batch, serialised, or passed directly to the
 * @google-cloud/spanner `Table.insert()` method once the SDK is wired.
 *
 * @example
 * ```ts
 * import { COMMIT_TIMESTAMP_SENTINEL } from './types.js';
 *
 * const mutation = generateSpannerInsertMutation({
 *   TraceId:         'f47ac10b-58cc-4372-a567-0e02b2c3d479',
 *   EventPayload:    JSON.stringify({ model: 'gpt-4o', tokens: 1024 }),
 *   AuditMode:       true,
 *   CommitTimestamp: COMMIT_TIMESTAMP_SENTINEL,
 * });
 * // → { table: 'CryptographicAnomalyRecords', columns: [...], values: [[...]] }
 * ```
 */
export function generateSpannerInsertMutation(
  record: CryptographicAnomalyRecord,
): SpannerInsertMutation {
  return {
    table: TABLE,
    columns: COLUMNS,
    values: [
      [
        record.TraceId,
        record.EventPayload,
        record.AuditMode,
        record.CommitTimestamp,
      ],
    ],
  };
}
