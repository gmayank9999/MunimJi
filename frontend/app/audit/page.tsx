import { Header } from "@/components/Header";

export default function AuditPage() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <h1 className="mb-4 text-lg font-semibold">Swytchcode Audit</h1>
        <p className="text-sm text-muted">
          Wired once <code className="font-mono">/api/audit</code> is live — will show every Swytchcode call,
          per-integration counts, and policy blocks.
        </p>
      </main>
    </div>
  );
}
