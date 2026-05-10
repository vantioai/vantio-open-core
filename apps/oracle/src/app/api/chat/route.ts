import { streamText } from 'ai'
import { openai } from '@ai-sdk/openai'

export async function POST(req: Request) {
  const { messages } = await req.json() as { messages: unknown[] }

  const result = await streamText({
    model: openai('gpt-4o'),
    messages: messages as Parameters<typeof streamText>[0]['messages'],
  })

  return result.toDataStreamResponse()
}
