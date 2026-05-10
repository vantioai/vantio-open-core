import { streamText, tool } from 'ai'
import { openai } from '@ai-sdk/openai'
import { z } from 'zod'
import { VantioInterceptor, type TelemetryPayload } from '@vantio/agent-sdk'
import { db } from '@/lib/db'
import { auth } from '@/auth'

const AGENT_ID = process.env.VANTIO_AGENT_ID || 'oracle-chat-node-01'

const interceptor = new VantioInterceptor({
  agentId: AGENT_ID,
  environment: process.env.NODE_ENV === 'production' ? 'production' : 'development',
})

export async function POST(req: Request) {
  const session = await auth()
  if (!session?.user?.id) {
    return new Response('Unauthorized', { status: 401 })
  }

  const { messages, threadId } = await req.json() as {
    messages: Parameters<typeof streamText>[0]['messages']
    threadId?: string
  }

  const latestMessage = messages[messages.length - 1]

  let activeThreadId = threadId
  if (!activeThreadId) {
    const thread = await db.chatThread.create({
      data: { userId: session.user.id },
    })
    activeThreadId = thread.id
  }

  await db.chatMessage.create({
    data: {
      threadId: activeThreadId,
      role: latestMessage.role,
      content: typeof latestMessage.content === 'string'
        ? latestMessage.content
        : JSON.stringify(latestMessage.content),
    },
  })

  const result = await streamText({
    model: openai('gpt-4o'),
    messages,
    tools: {
      getExecutionLedgerStatus: tool({
        description:
          'Retrieve the latest telemetry execution logs and token usage from the deterministic SQLite substrate. Use this when the user asks about system status, token usage, or recent telemetry.',
        parameters: z.object({
          limit: z.number().min(1).max(10).describe('Number of logs to retrieve'),
        }),
        execute: async ({ limit }) => {
          const logs = await db.telemetryLog.findMany({
            take: limit,
            orderBy: { createdAt: 'desc' },
          })
          return { status: 'success', data: logs }
        },
      }),
    },
    async onFinish({ usage, text }) {
      if (text) {
        await db.chatMessage.create({
          data: {
            threadId: activeThreadId as string,
            role: 'assistant',
            content: text,
          },
        })
      }

      const payload: TelemetryPayload & Record<string, unknown> = {
        executionTimeMs: 0,
        tokensConsumed: usage.totalTokens,
        modelIdentifier: 'gpt-4o',
        systemAction: 'llm_stream_completion',
        deterministicStatus: 'success',
      }

      const receipt = interceptor.recordExecution(payload)
      const traceId = process.env.VANTIO_TRACE_ID ?? receipt.traceId ?? undefined

      await db.telemetryLog.create({
        data: {
          agentId: AGENT_ID,
          traceId: traceId ?? null,
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
