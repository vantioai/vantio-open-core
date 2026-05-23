import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Welcome to Vantio AI PRO",
};

export default function SuccessPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-white px-6">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-green-50">
          <span className="text-3xl">✓</span>
        </div>
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
          Payment confirmed
        </p>
        <h1 className="mt-3 text-3xl font-bold text-gray-900">
          You&apos;re in the Phantom Engine.
        </h1>
        <p className="mt-4 text-sm text-gray-500">
          Your account has been upgraded to PRO. Your tenant record is now
          live in the Supabase ledger. Install the Phantom Engine to begin
          kernel-level enforcement.
        </p>

        <div className="mt-8 rounded-xl border border-gray-200 bg-gray-50 p-5 text-left">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Next: Install the Phantom Engine
          </p>
          <pre className="overflow-x-auto text-xs text-gray-700">
            <code>{`# In WSL (requires root)
git clone git@github.com:vantioai/vantio-phantom-engine.git
cd vantio-phantom-engine

# Build eBPF kernel crate
unset CARGO_TARGET_DIR
cargo build -p vantio-phantom-engine \\
  --target bpfel-unknown-none \\
  -Z build-std=core --release

# Build and run the loader
cargo build -p vantio-loader --release
sudo VANTIO_TRACE_ID=0x$(openssl rand -hex 8) \\
  ./target/release/vantio-loader`}</code>
          </pre>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/dashboard"
            className="rounded-lg bg-gray-900 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
          >
            Open Dashboard →
          </Link>
          <a
            href="https://github.com/vantioai/vantio-open-core"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-300 px-6 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-50"
          >
            SDK Docs
          </a>
        </div>
      </div>
    </main>
  );
}
