"use client";

import { useCallback, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { api, type Kpis } from "@/lib/api";
import { subscribeToRun, type TraceEvent } from "@/lib/sse";
import { PromptBar } from "./PromptBar";
import { DecisionCard, type DecisionEvent } from "./DecisionCard";
import { KpiStrip } from "./KpiStrip";
import { WhyPanel } from "./WhyPanel";
import { AgentGraphView, type RunPhase } from "./AgentGraphView";

interface RunSummary {
  invoices_scanned: number;
  counts_per_decision: Record<string, number>;
  exposure_inr: number;
}

export function RunConsole({ initialKpis }: { initialKpis: Kpis | null }) {
  const [kpis, setKpis] = useState<Kpis | null>(initialKpis);
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [decisions, setDecisions] = useState<DecisionEvent[]>([]);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [statusLine, setStatusLine] = useState<string>("Ask MunimJi to check your payments.");
  const [whyInvoiceId, setWhyInvoiceId] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const refreshKpis = useCallback(() => {
    api.kpis().then(setKpis).catch(() => {});
  }, []);

  const handleEvent = useCallback(
    (event: TraceEvent) => {
      if (event.type === "run.sensing") {
        setPhase("sensing");
        setStatusLine("Sensing live Stripe and Notion state…");
      } else if (event.type === "run.sensed") {
        const found = event.payload.invoices_in_scope as number;
        setStatusLine(`${found} invoice(s) in scope — deciding each one…`);
        setPhase("processing");
      } else if (event.type === "invoice.decided") {
        setPhase("processing");
        setDecisions((prev) => [event.payload as unknown as DecisionEvent, ...prev]);
      } else if (event.type === "run.finished") {
        setPhase("done");
        setSummary(event.payload as unknown as RunSummary);
        setStatusLine("Sweep finished.");
        refreshKpis();
        unsubscribeRef.current?.();
      } else if (event.type === "run.failed") {
        setPhase("failed");
        setStatusLine(`Run failed: ${event.payload.error}`);
        unsubscribeRef.current?.();
      }
    },
    [refreshKpis],
  );

  const handleRun = useCallback(
    async (prompt: string) => {
      unsubscribeRef.current?.();
      setDecisions([]);
      setSummary(null);
      setPhase("sensing");
      setStatusLine("Starting run…");
      try {
        const { run_id, intent } = await api.startRun(prompt);
        setStatusLine(intent.reasoning);
        unsubscribeRef.current = subscribeToRun(run_id, handleEvent);
      } catch {
        setPhase("failed");
        setStatusLine("Could not reach the backend. Is it running?");
      }
    },
    [handleEvent],
  );

  const running = phase === "sensing" || phase === "processing" || phase === "summarizing";

  return (
    <div className="flex flex-col gap-6">
      <PromptBar onRun={handleRun} running={running} />

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
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Live Decision Feed</h2>
            <span className="text-xs text-muted">{statusLine}</span>
          </div>
          {decisions.length === 0 && !running && (
            <p className="text-sm text-muted">
              Run a sweep to see MunimJi decide, per invoice, whether to wait, nudge, or escalate — with the
              Swytchcode-executed actions ticking in live.
            </p>
          )}
          <div className="flex flex-col gap-3">
            <AnimatePresence initial={false}>
              {decisions.map((d) => (
                <DecisionCard key={d.invoice_id} event={d} onWhy={setWhyInvoiceId} />
              ))}
            </AnimatePresence>
          </div>
          {summary && (
            <div className="mt-4 rounded-lg border border-saffron/30 bg-saffron/5 p-4 text-sm">
              <div className="font-semibold text-foreground">
                {summary.invoices_scanned} invoice(s) scanned
              </div>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                {Object.entries(summary.counts_per_decision).map(([decision, count]) => (
                  <span key={decision}>
                    {decision}: <span className="text-foreground">{count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
        <section className="rounded-xl border border-border bg-surface p-5 lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-foreground">Agent Graph</h2>
          <AgentGraphView phase={phase} />
          <p className="mt-2 text-xs text-muted">
            Supervisor → Sense → Invoice loop → Summary, across the Reasoning, Policy and Execution layers.
          </p>
        </section>
      </div>

      <WhyPanel invoiceId={whyInvoiceId} onClose={() => setWhyInvoiceId(null)} />
    </div>
  );
}
