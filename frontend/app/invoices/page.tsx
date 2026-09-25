import { DecisionPill } from "@/components/DecisionPill";
import { Header } from "@/components/Header";
import { api } from "@/lib/api";
import { formatDate, formatInr } from "@/lib/format";

export default async function InvoicesPage() {
  const invoices = await api.invoices().catch(() => []);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="mb-4 text-lg font-semibold">Invoices</h1>
        {invoices.length === 0 ? (
          <p className="text-sm text-muted">
            No invoices yet — run <code className="font-mono">make seed</code> once Swytchcode accounts are
            connected.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase text-muted">
                  <th className="px-4 py-3">Number</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Amount</th>
                  <th className="px-4 py-3">Due</th>
                  <th className="px-4 py-3">Due date</th>
                  <th className="px-4 py-3">Reminders</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Decision</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.invoice_id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-3 font-mono">{inv.number}</td>
                    <td className="px-4 py-3 text-muted">{inv.status}</td>
                    <td className="px-4 py-3 font-mono">{formatInr(inv.amount_inr)}</td>
                    <td className="px-4 py-3 font-mono">{formatInr(inv.due_inr)}</td>
                    <td className="px-4 py-3 text-muted">{formatDate(inv.due_date)}</td>
                    <td className="px-4 py-3 text-muted">{inv.reminder_count}</td>
                    <td className="px-4 py-3 text-muted">{inv.last_severity ?? "—"}</td>
                    <td className="px-4 py-3">
                      <DecisionPill decision={inv.last_decision} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
