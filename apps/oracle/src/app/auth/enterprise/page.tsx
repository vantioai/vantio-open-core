import { Button } from "@/components/ui/button"
import { authenticate } from "../actions"

export default function EnterpriseAuthPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-md space-y-8 rounded-lg border border-slate-200 bg-white p-10 shadow-sm">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Enterprise SAML Gateway
          </h1>
          <p className="text-sm text-slate-500">
            Authenticate via your corporate identity provider.
          </p>
        </div>
        <form action={authenticate} className="space-y-4">
          <div className="space-y-2">
            <input
              name="email"
              type="email"
              placeholder="Enterprise Email"
              required
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
            />
            <input
              name="domain"
              type="text"
              placeholder="Corporate Domain (e.g. vantio.ai)"
              required
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
            />
          </div>
          <Button type="submit" className="w-full" size="lg">
            Authenticate Payload
          </Button>
        </form>
        <div className="text-center text-xs text-slate-400 mt-8">
          Secured by Vantio AI Deterministic Architecture
        </div>
      </div>
    </div>
  )
}
