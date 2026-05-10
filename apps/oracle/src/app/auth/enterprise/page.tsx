import { Button } from "@/components/ui/button"

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
        <div className="space-y-4">
          <Button className="w-full" size="lg">
            Continue with Google Workspace
          </Button>
          <Button variant="outline" className="w-full" size="lg">
            Continue with Okta / Entra ID
          </Button>
        </div>
        <div className="text-center text-xs text-slate-400 mt-8">
          Secured by Vantio AI Deterministic Architecture
        </div>
      </div>
    </div>
  )
}
