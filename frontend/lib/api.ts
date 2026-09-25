const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Kpis {
  outstanding_inr: number;
  overdue_inr: number;
  avg_days_overdue: number;
  decisions_today: number;
  swytchcode_calls_today: number;
  policy_blocks_today: number;
  duplicates_prevented_today: number;
}

export interface PolicyResponse {
  config: Record<string, unknown>;
  decision_table_markdown: string;
}

export interface InvoiceRow {
  invoice_id: string;
  number: string;
  client_id: string;
  status: string;
  amount_inr: number;
  due_inr: number;
  invoice_date: string;
  due_date: string;
  reminder_count: number;
  state: string | null;
  last_decision: string | null;
  last_severity: number | null;
}

export interface ClientRow {
  client_id: string;
  name: string;
  email: string;
  tier: string;
  contact_name: string;
  relationship_notes: string | null;
  paused_until: string | null;
}

export interface RunRow {
  run_id: string;
  prompt: string;
  source: string;
  intent: string | null;
  clock_offset_days: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary_json: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => getJson<{ status: string; demo_mode: boolean; swytchcode_configured: boolean }>("/api/health"),
  kpis: () => getJson<Kpis>("/api/kpis"),
  policy: () => getJson<PolicyResponse>("/api/policy"),
  invoices: () => getJson<InvoiceRow[]>("/api/invoices"),
  invoiceTrace: (invoiceId: string) => getJson<Record<string, unknown>[]>(`/api/invoices/${invoiceId}/trace`),
  clients: () => getJson<ClientRow[]>("/api/clients"),
  runs: () => getJson<RunRow[]>("/api/runs"),
  run: (runId: string) => getJson<RunRow>(`/api/runs/${runId}`),
};

export { API_BASE };
