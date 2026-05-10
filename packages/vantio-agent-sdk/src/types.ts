/**
 * VANTIO SDK: DETERMINISTIC TYPE MATRIX
 * Enforces the Payload Quarantine by physically omitting prompt primitives.
 */
export interface VantioConfig {
  agentId: string;
  environment: 'development' | 'production' | 'vantio_audit_mode';
}

export interface TelemetryPayload {
  executionTimeMs: number;
  tokensConsumed: number;
  modelIdentifier: string;
  // The Payload Quarantine: 'prompt' and 'response' strings are explicitly banned from this interface.
  systemAction: string;
  deterministicStatus: 'success' | 'quarantined' | 'failed';
  traceId?: string;
}
