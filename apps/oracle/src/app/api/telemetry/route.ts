import { NextResponse } from 'next/server'
import { VantioInterceptor, type TelemetryPayload } from '@vantio/agent-sdk'
import { db } from '@/lib/db'

const agentId = process.env.VANTIO_AGENT_ID || 'oracle-edge-node-01'

const interceptor = new VantioInterceptor({
  agentId,
  environment: process.env.NODE_ENV === 'production' ? 'production' : 'development',
})

export async function POST(request: Request) {
  try {
    const body = await request.json() as TelemetryPayload & Record<string, unknown>

    // Enforce the physical quarantine matrix
    const receipt = interceptor.recordExecution(body)

    // Write valid telemetry to the deterministic substrate
    const traceId = process.env.VANTIO_TRACE_ID ?? body.traceId ?? receipt.traceId
    await db.telemetryLog.create({
      data: {
        agentId,
        traceId: typeof traceId === 'string' ? traceId : null,
        executionTimeMs: body.executionTimeMs,
        tokensConsumed: body.tokensConsumed,
        modelIdentifier: body.modelIdentifier,
        systemAction: body.systemAction,
        deterministicStatus: body.deterministicStatus,
      },
    })

    return NextResponse.json({ success: true, receipt }, { status: 200 })
  } catch (error: unknown) {
    const details = error instanceof Error ? error.message : 'Unknown fatal error'
    return NextResponse.json(
      { error: 'VANTIO_FATAL', details },
      { status: 403 }
    )
  }
}
