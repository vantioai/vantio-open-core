import { NextResponse } from 'next/server';
import { VantioInterceptor, type TelemetryPayload } from '@vantio/agent-sdk'

// Instantiate the Tier-01 Interceptor at the Edge
const interceptor = new VantioInterceptor({
  agentId: process.env.VANTIO_AGENT_ID || 'oracle-edge-node-01',
  environment: process.env.NODE_ENV === 'production' ? 'production' : 'development',
});

export async function POST(request: Request) {
  try {
    const body = await request.json() as TelemetryPayload & Record<string, unknown>;

    // Enforce the physical quarantine matrix
    const receipt = interceptor.recordExecution(body);

    return NextResponse.json({ success: true, receipt }, { status: 200 });
  } catch (error: unknown) {
    // Deterministic failure if Payload Quarantine is breached
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { error: 'VANTIO_FATAL', details: message },
      { status: 403 }
    );
  }
}
