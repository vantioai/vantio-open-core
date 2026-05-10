"use client"

import { useChat } from '@ai-sdk/react'
import { Button } from "@/components/ui/button"

export function ChatInterface() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat()

  return (
    <div className="flex flex-col h-[500px] w-full rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-500">
            Awaiting input for LLM streaming gateway...
          </div>
        ) : (
          messages.map(m => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-md px-4 py-2 text-sm ${m.role === 'user' ? 'bg-slate-900 text-slate-50' : 'bg-slate-100 text-slate-900'}`}>
                {m.content}
              </div>
            </div>
          ))
        )}
      </div>
      <form onSubmit={handleSubmit} className="flex p-4 border-t border-slate-200 bg-slate-50 gap-2">
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="Transmit payload to gpt-4o..."
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
          disabled={isLoading}
        />
        <Button type="submit" disabled={isLoading || !input.trim()}>
          Execute
        </Button>
      </form>
    </div>
  )
}
