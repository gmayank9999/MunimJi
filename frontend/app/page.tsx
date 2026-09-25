import { Header } from "@/components/Header";
import { KpiStrip } from "@/components/KpiStrip";
import { api } from "@/lib/api";

export default async function Home() {
  const kpis = await api.kpis().catch(() => null);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
        <div className="rounded-xl border border-border bg-surface px-5 py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              type="text"
              placeholder='Ask MunimJi&hellip; "Check all pending PayPal transactions and take necessary action"'
              className="flex-1 rounded-lg border border-border bg-background px-4 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-saffron"
              disabled
            />
            <button
              type="button"
              disabled
              className="rounded-lg bg-saffron px-4 py-2 text-sm font-medium text-background opacity-60"
            >
              Run
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
            {[
              "Check all payments",
              "Why did you escalate Orion?",
              "What's my exposure?",
              "Pause Bluepeak till Monday",
              "What happens in 7 days?",
            ].map((chip) => (
              <span key={chip} className="rounded-full border border-border px-3 py-1">
                {chip}
              </span>
            ))}
          </div>
        </div>

        {kpis ? (
          <KpiStrip kpis={kpis} />
        ) : (
          <div className="rounded-xl border border-border bg-surface px-5 py-4 text-sm text-muted">
            Backend not reachable at the configured API URL. Start it with{" "}
            <code className="font-mono text-foreground">uvicorn app.main:app --reload</code> in{" "}
            <code className="font-mono text-foreground">backend/</code>.
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <section className="rounded-xl border border-border bg-surface p-5 lg:col-span-3">
            <h2 className="mb-3 text-sm font-semibold text-foreground">Live Decision Feed</h2>
            <p className="text-sm text-muted">
              Run a sweep to see MunimJi decide, per invoice, whether to wait, nudge, or escalate — with the
              Swytchcode-executed actions ticking in live.
            </p>
          </section>
          <section className="rounded-xl border border-border bg-surface p-5 lg:col-span-2">
            <h2 className="mb-3 text-sm font-semibold text-foreground">Agent Graph</h2>
            <p className="text-sm text-muted">
              Supervisor → Sense → Invoice loop → Summary, across the Reasoning, Policy and Execution
              layers.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
