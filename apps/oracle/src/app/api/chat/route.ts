import { streamText } from 'ai'
import { openai } from '@ai-sdk/openai'
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

  // Deterministically anchor the thread
  let activeThreadId = threadId
  if (!activeThreadId) {
    const thread = await db.chatThread.create({
      data: { userId: session.user.id },
    })
    activeThreadId = thread.id
  }

  // Persist the user's incoming payload
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
    async onFinish({ usage, text }) {
      // Persist the AI's response
      await db.chatMessage.create({
        data: {
          threadId: activeThreadId as string,
          role: 'assistant',
          content: text,
        },
      })

      // Transmit metadata through the Telemetry Quarantine
      const payload: TelemetryPayload & Record<string, unknown> = {
        executionTimeMs: 0,
        tokensConsumed: usage.totalTokens,
        modelIdentifier: 'gpt-4o',
        systemAction: 'llm_stream_completion',
        deterministicStatus: 'success',
      }

      interceptor.recordExecution(payload)

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
