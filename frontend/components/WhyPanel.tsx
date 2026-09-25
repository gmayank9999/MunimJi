"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, type DecisionTraceRow } from "@/lib/api";
import { formatInr } from "@/lib/format";
import { DecisionPill } from "./DecisionPill";
import { SeverityBar } from "./SeverityBar";

interface Facts {
  client_name: string;
  number: string;
  days_overdue: number;
  amount_inr: number;
  due_inr: number;
  promise_status: string;
  reminder_count: number;
  client_tier: string;
}

interface Signal {
  category: string;
  key_quote: string;
  sentiment: string;
}

interface FetchedTrace {
  invoiceId: string;
  trace: DecisionTraceRow | null;
}

export function WhyPanel({ invoiceId, onClose }: { invoiceId: string | null; onClose: () => void }) {
  const [fetched, setFetched] = useState<FetchedTrace | null>(null);

  useEffect(() => {
    if (!invoiceId) return;
    let cancelled = false;
    api.invoiceTrace(invoiceId).then((rows) => {
      if (!cancelled) setFetched({ invoiceId, trace: rows.length > 0 ? rows[rows.length - 1] : null });
    });
    return () => {
      cancelled = true;
    };
  }, [invoiceId]);

  const trace = fetched?.invoiceId === invoiceId ? fetched.trace : null;
  const loading = invoiceId !== null && fetched?.invoiceId !== invoiceId;

  const facts: Facts | null = trace ? JSON.parse(trace.facts_json) : null;
  const signal: Signal | null = trace ? JSON.parse(trace.signal_json) : null;
  const severityBreakdown: Record<string, number> | null = trace
    ? JSON.parse(trace.severity_breakdown_json)
    : null;
  const reasons: string[] = trace ? JSON.parse(trace.reasons_json) : [];
  const counterfactuals: string[] = trace?.counterfactuals_json ? JSON.parse(trace.counterfactuals_json) : [];

  return (
    <AnimatePresence>
      {invoiceId && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50"
            onClick={onClose}
          />
          <motion.aside
            key="panel"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", duration: 0.25 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto border-l border-border bg-surface p-6"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">Why this decision?</h2>
              <button type="button" onClick={onClose} className="text-muted hover:text-foreground">
                ✕
              </button>
            </div>

            {loading && <p className="mt-6 text-sm text-muted">Loading trace…</p>}

            {!loading && trace && facts && (
              <div className="mt-5 flex flex-col gap-5">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-mono text-sm text-foreground">{facts.number}</div>
                    <div className="text-xs text-muted">
                      {facts.client_name} · {facts.client_tier}
                    </div>
                  </div>
                  <DecisionPill decision={trace.decision} />
                </div>

                <p className="text-sm text-foreground/90">{trace.explanation}</p>

                <section>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Facts</h3>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    <dt className="text-muted">Amount due</dt>
                    <dd className="text-right font-mono text-foreground">{formatInr(facts.due_inr)}</dd>
                    <dt className="text-muted">Days overdue</dt>
                    <dd className="text-right font-mono text-foreground">{facts.days_overdue}</dd>
                    <dt className="text-muted">Reminders sent</dt>
                    <dd className="text-right font-mono text-foreground">{facts.reminder_count}</dd>
                    <dt className="text-muted">Promise status</dt>
                    <dd className="text-right font-mono text-foreground">{facts.promise_status}</dd>
                  </dl>
                </section>

                {signal && (
                  <section>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                      Client signal
                    </h3>
                    <p className="text-xs text-muted">
                      Category: <span className="text-foreground">{signal.category}</span>
                      {signal.key_quote && (
                        <>
                          {" "}
                          — &ldquo;<span className="italic text-foreground/80">{signal.key_quote}</span>&rdquo;
                        </>
                      )}
                    </p>
                  </section>
                )}

                {severityBreakdown && (
                  <section>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                      Severity breakdown ({trace.severity})
                    </h3>
                    <SeverityBar breakdown={severityBreakdown} />
                  </section>
                )}

                <section>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                    Rule {trace.rule_id}
                  </h3>
                  <ul className="list-inside list-disc text-xs text-foreground/90">
                    {reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </section>

                {counterfactuals.length > 0 && (
                  <section>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                      What would change this
                    </h3>
                    <ul className="list-inside list-disc text-xs text-foreground/90">
                      {counterfactuals.map((hint) => (
                        <li key={hint}>{hint}</li>
                      ))}
                    </ul>
                  </section>
                )}

                <p className="text-[11px] text-muted">
                  The LLM reads and writes. The policy engine decides — this trace is deterministic and
                  reproducible from the facts above.
                </p>
              </div>
            )}

            {!loading && !trace && <p className="mt-6 text-sm text-muted">No decision trace yet.</p>}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
