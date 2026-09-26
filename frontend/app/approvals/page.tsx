"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { api, type PendingApproval } from "@/lib/api";

interface EmailPayload {
  to?: string;
  subject?: string;
  body?: string;
}

const POLL_MS = 5000;

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .approvals()
      .then((rows) => {
        setApprovals(rows);
        setError(null);
      })
      .catch(() => setError("Backend not reachable."));
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleApprove(idemKey: string) {
    setBusyKey(idemKey);
    try {
      await api.approve(idemKey);
    } finally {
      setBusyKey(null);
      refresh();
    }
  }

  async function handleReject(idemKey: string) {
    setBusyKey(idemKey);
    try {
      await api.reject(idemKey);
    } finally {
      setBusyKey(null);
      refresh();
    }
  }

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-semibold">Approvals</h1>
          <span className="text-xs text-muted">Nothing sends without a ✅ here.</span>
        </div>

        {error && <p className="text-sm text-muted">{error}</p>}

        {!error && approvals.length === 0 && (
          <p className="text-sm text-muted">
            Nothing parked right now — VIP reminders, escalation emails and refund proposals will show up
            here for review before they go out.
          </p>
        )}

        <div className="flex flex-col gap-3">
          {approvals.map((row) => {
            const payload: EmailPayload = row.payload_json ? JSON.parse(row.payload_json) : {};
            const busy = busyKey === row.idem_key;
            return (
              <div key={row.idem_key} className="rounded-xl border border-border bg-surface p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-mono text-xs text-muted">{row.action_type}</span>
                    <span className="ml-2 rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted">
                      {row.tool}
                    </span>
                  </div>
                  <span className="text-xs text-muted">to {payload.to}</span>
                </div>
                {payload.subject && (
                  <div className="mt-2 text-sm font-medium text-foreground">{payload.subject}</div>
                )}
                {payload.body && (
                  <pre className="mt-1 whitespace-pre-wrap font-sans text-sm text-foreground/80">
                    {payload.body}
                  </pre>
                )}
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleApprove(row.idem_key)}
                    className="rounded-lg bg-decision-close px-4 py-1.5 text-sm font-medium text-background disabled:opacity-50"
                  >
                    ✅ Approve &amp; send
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleReject(row.idem_key)}
                    className="rounded-lg border border-border px-4 py-1.5 text-sm text-muted hover:text-foreground disabled:opacity-50"
                  >
                    ❌ Reject
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}
