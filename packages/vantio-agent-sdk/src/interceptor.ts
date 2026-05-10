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
    // THE PAYLOAD QUARANTINE: Runtime Enforcement
    if ('prompt' in payload || 'raw_input' in payload || 'completion' in payload) {
      throw new Error("VANTIO_FATAL: Payload Quarantine Violation. Raw linguistic payloads cannot traverse the telemetry boundary.");
    }

    // Phase 3: Dynamically capture the CLI-injected Trace ID
    const traceId = typeof process !== 'undefined' && process.env.VANTIO_TRACE_ID
      ? process.env.VANTIO_TRACE_ID
      : undefined;

    const finalPayload = { ...payload, traceId };

    if (this.config.environment === 'development') {
      console.log(`[VANTIO TIER-01] Execution recorded deterministically for agent: ${this.config.agentId}`);
      if (traceId) console.log(`[VANTIO TIER-01] Linked to CLI Trace: ${traceId}`);
    }

    // In a production state, this transmits asynchronously to the Edge Proxy.
    // For Tier-01, we return the payload so the local route handler can ingest it.
    return { status: 'acknowledged', timestamp: Date.now(), traceId: finalPayload.traceId };
  }
}
