import type { CryptographicAnomalyRecord } from "./types.js";

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
    AnomalyMetadata: string | null,
    AuditMode: boolean,
    CommitTimestamp: CryptographicAnomalyRecord["CommitTimestamp"],
  ]>;
}

const TABLE = "CryptographicAnomalyRecords" as const;

// Column order must stay in sync with schema.ddl and CryptographicAnomalyRecord.
const COLUMNS = [
  "TraceId",
  "AnomalyMetadata",
  "AuditMode",
  "CommitTimestamp",
] as const;

/**
 * Produces a deterministic, column-ordered Spanner insert mutation object for
 * a single `CryptographicAnomalyRecords` row.
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
        record.AnomalyMetadata,
        record.AuditMode,
        record.CommitTimestamp,
      ],
    ],
  };
}
