"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"

export function TelemetryDispatcher() {
  const [status, setStatus] = React.useState<string>("SYSTEM IDLE")

  const fireValidPayload = async () => {
    setStatus("TRANSMITTING VALID PAYLOAD...")
    const res = await fetch('/api/telemetry', {
      method: 'POST',
      body: JSON.stringify({
        executionTimeMs: 142,
        tokensConsumed: 850,
        modelIdentifier: "claude-3-opus",
        systemAction: "data_normalization",
        deterministicStatus: "success"
      })
    })
    const data = await res.json() as { receipt?: unknown; error?: string }
    setStatus(res.ok ? `SUCCESS: ${JSON.stringify(data.receipt)}` : `ERROR: ${data.error}`)
  }

  const fireQuarantinedPayload = async () => {
    setStatus("TRANSMITTING QUARANTINED PAYLOAD...")
    const res = await fetch('/api/telemetry', {
      method: 'POST',
      body: JSON.stringify({
        executionTimeMs: 88,
        tokensConsumed: 120,
        modelIdentifier: "claude-3-opus",
        systemAction: "user_query",
        deterministicStatus: "quarantined",
        prompt: "What is the capital of France?"
      })
    })
    const data = await res.json() as { error?: string; details?: string }
    setStatus(res.ok ? "CRITICAL FAILURE: QUARANTINE BREACHED" : `BLOCKED: ${data.error} - ${data.details}`)
  }

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="text-lg font-semibold tracking-tight text-slate-900">Tier-01 Telemetry Diagnostics</h3>
      <div className="flex space-x-4">
        <Button onClick={fireValidPayload}>Test Valid Telemetry</Button>
        <Button variant="outline" onClick={fireQuarantinedPayload}>Test Payload Quarantine</Button>
      </div>
      <div className="mt-4 rounded bg-slate-950 p-4 text-xs font-mono text-emerald-400 break-words">
        {status}
      </div>
    </div>
  )
}
