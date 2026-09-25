import { Header } from "@/components/Header";
import { api } from "@/lib/api";

const TIER_COLORS: Record<string, string> = {
  VIP: "bg-saffron/15 text-saffron border-saffron/30",
  Regular: "bg-surface text-foreground border-border",
  New: "bg-decision-followup/15 text-decision-followup border-decision-followup/30",
  Watchlist: "bg-decision-escalate/15 text-decision-escalate border-decision-escalate/30",
};

export default async function ClientsPage() {
  const clients = await api.clients().catch(() => []);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="mb-4 text-lg font-semibold">Clients</h1>
        {clients.length === 0 ? (
          <p className="text-sm text-muted">
            No clients yet — run <code className="font-mono">make seed</code> once Swytchcode accounts are
            connected.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {clients.map((client) => (
              <div key={client.client_id} className="rounded-xl border border-border bg-surface p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{client.name}</span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs ${TIER_COLORS[client.tier] ?? "border-border text-muted"}`}
                  >
                    {client.tier}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted">{client.contact_name}</p>
                <p className="mt-1 text-xs text-muted">{client.email}</p>
                {client.paused_until && (
                  <p className="mt-2 text-xs text-decision-wait">Paused until {client.paused_until}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
