import type { Kpis } from "@/lib/api";
import { formatInr } from "@/lib/format";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
      <span className="font-mono text-lg text-foreground">{value}</span>
    </div>
  );
}

export function KpiStrip({ kpis }: { kpis: Kpis }) {
  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-3 rounded-xl border border-border bg-surface px-5 py-4">
      <Stat label="Outstanding" value={formatInr(kpis.outstanding_inr)} />
      <Stat label="Overdue" value={formatInr(kpis.overdue_inr)} />
      <Stat label="Avg days overdue" value={kpis.avg_days_overdue.toFixed(1)} />
      <Stat label="Decisions today" value={String(kpis.decisions_today)} />
      <Stat label="Swytchcode calls" value={String(kpis.swytchcode_calls_today)} />
      <Stat label="Policy blocks" value={String(kpis.policy_blocks_today)} />
      <Stat label="Duplicates prevented" value={String(kpis.duplicates_prevented_today)} />
    </div>
  );
}
