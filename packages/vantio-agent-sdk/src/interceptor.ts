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

    // In a production state, this transmits asynchronously to the Tier 02 Edge Proxy
    if (this.config.environment === 'development') {
      console.log(`[VANTIO TIER-01] Execution recorded deterministically for agent: ${this.config.agentId}`);
    }

    return { status: 'acknowledged', timestamp: Date.now() };
  }
}
