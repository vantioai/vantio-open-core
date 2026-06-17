-- Vantio AI — TrueTime Ledger
-- Control Plane: @vantio/edge-proxy (Enterprise Tier 3 Managed Governance Layer)
--
-- Telemetry ingestion table for cryptographic anomaly events.
-- CommitTimestamp uses server-side TrueTime assignment via
-- allow_commit_timestamp=true, guaranteeing strict external consistency
-- across all multi-tenant ingestion writers.
--
-- Payload Quarantine: AnomalyMetadata is strictly deterministic execution
-- context only (PID, bytes, target host, action taken, timestamp).
-- Linguistic content (prompts, responses, PII) is NEVER stored here.

CREATE TABLE CryptographicAnomalyRecords (
  TraceId         STRING(36)   NOT NULL,
  AnomalyMetadata JSON,                    -- bytes_severed, pid, target_host, action_taken, timestamp_ns
  AuditMode       BOOL         NOT NULL,
  CommitTimestamp TIMESTAMP    NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY (TraceId, CommitTimestamp);
