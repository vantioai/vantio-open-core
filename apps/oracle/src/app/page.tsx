export const dynamic = "force-dynamic"

import { redirect } from "next/navigation"
import { auth, signOut } from "@/auth"
import { db } from "@/lib/db"
import { Button } from "@/components/ui/button"
import { TelemetryDispatcher } from "@/components/telemetry-dispatcher"
import { ChatInterface } from "@/components/chat-interface"

export default async function Home() {
  const session = await auth()

  if (!session?.user?.id) {
    redirect("/auth/enterprise")
  }

  const logs = await db.telemetryLog.findMany({
    orderBy: { createdAt: "desc" },
    take: 5,
  })

  const activeThread = await db.chatThread.findFirst({
    where: { userId: session.user.id },
    include: { messages: { orderBy: { createdAt: "asc" } } },
    orderBy: { updatedAt: "desc" },
  })

  const initialMessages = activeThread?.messages.map(m => ({
    id: m.id,
    role: m.role as "user" | "assistant" | "system" | "data",
    content: m.content,
  })) ?? []

  return (
    <main className="flex min-h-screen flex-col items-center p-12 bg-slate-50">
      <div className="w-full max-w-4xl space-y-8">
        <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">The Omniscient Oracle</h1>
            <p className="text-slate-500">Tier-01 Edge Control Plane</p>
          </div>
          <div className="text-right">
            <div className="text-sm font-medium text-slate-900">{session.user.email}</div>
            <div className="text-xs text-slate-500 mb-2">{session.user.name}</div>
            <form
              action={async () => {
                "use server"
                await signOut({ redirectTo: "/auth/enterprise" })
              }}
            >
              <Button variant="outline" size="sm" className="h-7 text-xs">
                Sever Session
              </Button>
            </form>
          </div>
        </div>

        <ChatInterface initialMessages={initialMessages} threadId={activeThread?.id} />
        <TelemetryDispatcher />

        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold tracking-tight text-slate-900">Live Execution Ledger</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-100 text-slate-600 text-xs uppercase">
                <tr>
                  <th className="px-4 py-2 rounded-tl-md">Timestamp</th>
                  <th className="px-4 py-2">Action</th>
                  <th className="px-4 py-2">Model</th>
                  <th className="px-4 py-2">Tokens</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2 rounded-tr-md">Trace ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-4 text-center text-slate-500">
                      No telemetry recorded.
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3 font-mono text-xs">
                        {log.createdAt.toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-3">{log.systemAction}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">
                        {log.modelIdentifier}
                      </td>
                      <td className="px-4 py-3 text-right">{log.tokensConsumed}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">
                          {log.deterministicStatus}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-400 truncate max-w-[160px]">
                        {log.traceId ?? <span className="italic">unlinked</span>}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  )
}
