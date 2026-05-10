import { streamText } from 'ai'
import { openai } from '@ai-sdk/openai'
import { VantioInterceptor, type TelemetryPayload } from '@vantio/agent-sdk'
import { db } from '@/lib/db'

const AGENT_ID = process.env.VANTIO_AGENT_ID || 'oracle-chat-node-01'

const interceptor = new VantioInterceptor({
  agentId: AGENT_ID,
  environment: process.env.NODE_ENV === 'production' ? 'production' : 'development',
})

export async function POST(req: Request) {
  const { messages } = await req.json() as { messages: Parameters<typeof streamText>[0]['messages'] }

  const result = await streamText({
    model: openai('gpt-4o'),
    messages,
    async onFinish({ usage }) {
      const payload: TelemetryPayload & Record<string, unknown> = {
        executionTimeMs: 0,
        tokensConsumed: usage.totalTokens,
        modelIdentifier: 'gpt-4o',
        systemAction: 'llm_stream_completion',
        deterministicStatus: 'success',
      }

      // Pass through the SDK quarantine check
      interceptor.recordExecution(payload)

      // Persist the executed tokens to the Vantio ledger
      await db.telemetryLog.create({
        data: {
          agentId: AGENT_ID,
          executionTimeMs: 0,
          tokensConsumed: usage.totalTokens,
          modelIdentifier: 'gpt-4o',
          systemAction: 'llm_stream_completion',
          deterministicStatus: 'success',
        },
      })
    },
  })

  return result.toDataStreamResponse()
}
