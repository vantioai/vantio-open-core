-- Vantio AI — TrueTime Ledger
-- Control Plane: @vantio/edge-proxy (PRO/SMB Managed Governance Layer)
--
-- Telemetry ingestion table for cryptographic anomaly events.
-- CommitTimestamp uses server-side TrueTime assignment via
-- allow_commit_timestamp=true, guaranteeing strict external consistency
-- across all multi-tenant ingestion writers.

CREATE TABLE CryptographicAnomalyRecords (
  TraceId         STRING(36)   NOT NULL,
  EventPayload    STRING(MAX),
  AuditMode       BOOL         NOT NULL,
  CommitTimestamp TIMESTAMP    NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY (TraceId, CommitTimestamp);
