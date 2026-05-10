import { VantioConfig, TelemetryPayload } from './types';

export class VantioInterceptor {
  private config: VantioConfig;

  constructor(config: VantioConfig) {
    if (!config.agentId) {
      throw new Error("VANTIO_FATAL: Agent Identity missing. Cannot establish telemetry boundary.");
    }
    this.config = config;
  }

  public recordExecution(payload: TelemetryPayload & Record<string, unknown>) {
    if ('prompt' in payload || 'raw_input' in payload || 'completion' in payload) {
      throw new Error("VANTIO_FATAL: Payload Quarantine Violation. Raw linguistic payloads cannot traverse the telemetry boundary.");
    }

    const traceId = typeof process !== 'undefined' && process.env.VANTIO_TRACE_ID
      ? process.env.VANTIO_TRACE_ID
      : undefined;

    const isCloudIngest =
      typeof process !== 'undefined' && process.env.VANTIO_CLOUD_INGEST === 'true';

    const finalPayload = { ...payload, traceId };

    if (isCloudIngest) {
      // Asynchronous non-blocking transmission to Tier-2 SaaS infrastructure
      this.transmitToCloud(finalPayload);
      return { status: 'routed_to_cloud' as const, timestamp: Date.now(), traceId };
    }

    // Default to local ephemeral routing
    if (this.config.environment === 'development') {
      console.log(`[VANTIO TIER-01] Execution recorded locally for agent: ${this.config.agentId}`);
      if (traceId) console.log(`[VANTIO TIER-01] Linked to CLI Trace: ${traceId}`);
    }

    return { status: 'acknowledged' as const, timestamp: Date.now(), traceId };
  }

  private transmitToCloud(payload: TelemetryPayload & Record<string, unknown>) {
    // Stub implementation for Tier-2 ingestion.
    // In production, this posts to api.vantio.com via native fetch.
    const apiKey = typeof process !== 'undefined' ? process.env.VANTIO_API_KEY : undefined;
    if (!apiKey) {
      console.warn("[VANTIO SDK] Failed to transmit: Missing VANTIO_API_KEY");
      return;
    }
    const traceId = payload.traceId ?? 'unlinked';
    console.log(`[VANTIO SDK] Transmitting trace ${traceId} to The Omniscient Oracle (Tier-2).`);
  }
}
