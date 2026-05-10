import { TelemetryDispatcher } from "@/components/telemetry-dispatcher"

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-slate-50">
      <div className="w-full max-w-3xl space-y-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">The Omniscient Oracle</h1>
          <p className="text-slate-500">Tier-01 Edge Control Plane</p>
        </div>
        <TelemetryDispatcher />
      </div>
    </main>
  )
}
