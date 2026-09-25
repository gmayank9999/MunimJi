import { API_BASE } from "./api";

export interface TraceEvent {
  run_id: string;
  seq: number;
  ts: string;
  type: string;
  node: string;
  invoice_id: string | null;
  payload: Record<string, unknown>;
}

/** Subscribes to a run's SSE stream, replaying stored events then live ones. Dedupes by seq. */
export function subscribeToRun(runId: string, onEvent: (event: TraceEvent) => void): () => void {
  const source = new EventSource(`${API_BASE}/api/runs/${runId}/events`);
  const seenSeqs = new Set<number>();

  source.onmessage = (raw) => {
    if (!raw.data || raw.data === "{}") return; // heartbeat
    const event = JSON.parse(raw.data) as TraceEvent;
    if (seenSeqs.has(event.seq)) return;
    seenSeqs.add(event.seq);
    onEvent(event);
  };

  return () => source.close();
}
