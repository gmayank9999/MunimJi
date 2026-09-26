// Service worker: the only place that ever holds the extension key or calls the
// backend. Content scripts and the popup message this instead of fetching directly -
// per the same rule the rest of MunimJi follows, the UI layer never talks to a
// provider (or, here, the backend's trusted API) on its own.

const DEFAULT_API_BASE = "http://localhost:8000";

async function getConfig() {
  const stored = await chrome.storage.sync.get(["apiBase", "extKey"]);
  return {
    apiBase: stored.apiBase || DEFAULT_API_BASE,
    extKey: stored.extKey || "",
  };
}

async function apiFetch(path, options = {}) {
  const { apiBase, extKey } = await getConfig();
  const res = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "X-MunimJi-Ext-Key": extKey,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${path} -> ${res.status} ${body}`.trim());
  }
  return res.status === 204 ? null : res.json();
}

const HANDLERS = {
  "munimji:lookup": (msg) => apiFetch(`/api/ext/lookup?email=${encodeURIComponent(msg.email)}`),
  "munimji:approvals": () => apiFetch("/api/ext/approvals"),
  "munimji:approve": (msg) => apiFetch(`/api/ext/approvals/${encodeURIComponent(msg.idemKey)}/approve`, { method: "POST" }),
  "munimji:reject": (msg) => apiFetch(`/api/ext/approvals/${encodeURIComponent(msg.idemKey)}/reject`, { method: "POST" }),
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const handler = HANDLERS[message?.type];
  if (!handler) return false;

  handler(message)
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
  return true; // keep the message channel open for the async response above
});
