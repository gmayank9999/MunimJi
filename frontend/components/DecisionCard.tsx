"use client";

import { motion } from "framer-motion";
import { DecisionPill } from "./DecisionPill";
import { formatInr } from "@/lib/format";

export interface DecisionEvent {
  invoice_id: string;
  invoice_number: string;
  client_name: string;
  client_tier: string;
  decision: string;
  rule_id: string;
  severity: number;
  severity_band: string;
  explanation: string;
  reasons: string[];
  counterfactuals: string[];
  amount_inr: number;
  due_inr: number;
  days_overdue: number;
}

export function DecisionCard({
  event,
  onWhy,
}: {
  event: DecisionEvent;
  onWhy: (invoiceId: string) => void;
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="rounded-lg border border-border bg-background/40 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-foreground">{event.invoice_number}</span>
            <span className="text-xs text-muted">{event.client_name}</span>
            <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted">
              {event.client_tier}
            </span>
          </div>
          <span className="text-xs text-muted">
            {formatInr(event.due_inr)} due · {event.days_overdue} day(s) overdue · severity {event.severity} (
            {event.severity_band})
          </span>
        </div>
        <DecisionPill decision={event.decision} />
      </div>
      <p className="mt-2 text-sm text-foreground/90">{event.explanation}</p>
      <div className="mt-2 flex items-center justify-between">
        <span className="font-mono text-[11px] text-muted">rule {event.rule_id}</span>
        <button
          type="button"
          onClick={() => onWhy(event.invoice_id)}
          className="text-xs font-medium text-saffron hover:underline"
        >
          Why?
        </button>
      </div>
    </motion.div>
  );
}
