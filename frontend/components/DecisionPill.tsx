const DECISION_COLORS: Record<string, string> = {
  CLOSE: "bg-decision-close/15 text-decision-close border-decision-close/30",
  WAIT: "bg-decision-wait/15 text-decision-wait border-decision-wait/30",
  FOLLOWUP: "bg-decision-followup/15 text-decision-followup border-decision-followup/30",
  HIGH_PRIORITY: "bg-decision-high-priority/15 text-decision-high-priority border-decision-high-priority/30",
  ESCALATE: "bg-decision-escalate/15 text-decision-escalate border-decision-escalate/30",
  CRITICAL: "bg-decision-critical/15 text-decision-critical border-decision-critical/30",
  DISPUTE_ROUTE: "bg-decision-dispute/15 text-decision-dispute border-decision-dispute/30",
  RECONCILE: "bg-decision-reconcile/15 text-decision-reconcile border-decision-reconcile/30",
  HANDOVER: "bg-decision-recovery/15 text-decision-recovery border-decision-recovery/30",
};

const DECISION_ICONS: Record<string, string> = {
  CLOSE: "✅",
  WAIT: "⏸",
  FOLLOWUP: "✉️",
  HIGH_PRIORITY: "⚠️",
  ESCALATE: "🚨",
  CRITICAL: "🔴",
  DISPUTE_ROUTE: "⚖️",
  RECONCILE: "🔎",
  HANDOVER: "📞",
};

export function DecisionPill({ decision }: { decision: string | null }) {
  if (!decision) {
    return (
      <span className="inline-flex items-center rounded-full border border-border px-2.5 py-0.5 text-xs font-mono text-muted">
        {"—"}
      </span>
    );
  }
  const classes = DECISION_COLORS[decision] ?? "bg-surface text-muted border-border";
  const icon = DECISION_ICONS[decision] ?? "";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-mono font-medium ${classes}`}
    >
      <span>{icon}</span>
      {decision}
    </span>
  );
}
