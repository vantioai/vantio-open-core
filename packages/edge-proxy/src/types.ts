/**
 * Sentinel string accepted by the @google-cloud/spanner SDK in place of a
 * concrete timestamp value. When present in a mutation, Spanner assigns the
 * TrueTime commit timestamp server-side, guaranteeing strict external
 * consistency without requiring the client to supply a clock value.
 *
 * Corresponds to: TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
 */
export const COMMIT_TIMESTAMP_SENTINEL =
  "spanner.commit_timestamp()" as const;

export type CommitTimestampValue = Date | typeof COMMIT_TIMESTAMP_SENTINEL;

/**
 * Strict TypeScript mapping of the `CryptographicAnomalyRecords` Spanner
 * table defined in spanner/schema.ddl.
 *
 * Column mapping:
 *   TraceId         → STRING(36)   NOT NULL
 *   AnomalyMetadata → JSON                   (nullable — execution context only)
 *   AuditMode       → BOOL         NOT NULL
 *   CommitTimestamp → TIMESTAMP    NOT NULL  OPTIONS (allow_commit_timestamp=true)
 *
 * Payload Quarantine: AnomalyMetadata must never contain raw linguistic
 * content (prompts, model responses, PII). Only deterministic execution
 * context fields are permitted: bytes_severed, pid, target_host,
 * action_taken, timestamp_ns.
 */
export interface CryptographicAnomalyRecord {
  /**
   * UUID v4 trace identifier sourced from withVantio() in @vantio/agent-sdk.
   * Constrained to STRING(36) — no padding, no braces.
   */
  readonly TraceId: string;

  /**
   * JSON-serialised execution context metadata. NULL when no structured
   * context is available.
   *
   * Permitted fields only: bytes_severed, pid, target_host, action_taken,
   * timestamp_ns. Linguistic content is structurally forbidden.
   */
  readonly AnomalyMetadata: string | null;

  /**
   * Whether the originating execution context had VANTIO_AUDIT_MODE=1 set
   * by the @vantio/cli process supervisor at spawn time.
   */
  readonly AuditMode: boolean;

  /**
   * Spanner TrueTime commit timestamp.
   * Pass COMMIT_TIMESTAMP_SENTINEL to let Spanner assign server-side,
   * or supply a concrete Date for back-fill / replay scenarios.
   */
  readonly CommitTimestamp: CommitTimestampValue;
}
