// Injects a small 🪔 MunimJi badge into an open Gmail thread when one of the
// participants matches a known client. Everything renders inside a Shadow DOM so
// Gmail's own styles can never leak in or be clobbered by ours.
//
// Gmail is a single-page app with no full navigations and famously obfuscated,
// frequently-changing class names, so this deliberately avoids relying on any of
// them for anything load-bearing:
//  - participant emails come from `span[email]`, an attribute Gmail has attached to
//    sender/recipient chips for well over a decade (used by most Gmail extensions)
//  - the injection point tries a short list of fallback selectors and simply does
//    nothing if none match, rather than guessing at a brittle one and breaking Gmail
//
// This can't be exercised by an automated test - if the badge doesn't appear, check
// the selectors below against the current Gmail DOM (right-click the subject line ->
// Inspect) and adjust SUBJECT_SELECTORS.

const SUBJECT_SELECTORS = ["h2.hP", "[role='main'] h2", "[role='main'] [role='heading']"];
const BADGE_MARK = "data-munimji-lens";

function findInjectionPoint() {
  for (const selector of SUBJECT_SELECTORS) {
    const el = document.querySelector(selector);
    if (el) return el;
  }
  return null;
}

function currentParticipantEmails() {
  const nodes = document.querySelectorAll("span[email]");
  const emails = new Set();
  nodes.forEach((node) => {
    const email = node.getAttribute("email");
    if (email) emails.add(email.toLowerCase());
  });
  return [...emails];
}

function sendMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => resolve(response));
  });
}

function formatInr(amount) {
  const digits = Math.abs(Math.round(amount)).toString();
  if (digits.length <= 3) return `₹${digits}`;
  const last3 = digits.slice(-3);
  let rest = digits.slice(0, -3);
  const parts = [];
  while (rest.length > 2) {
    parts.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  if (rest) parts.unshift(rest);
  return `₹${parts.join(",")},${last3}`;
}

const DECISION_COLORS = {
  CLOSE: "#22c55e",
  WAIT: "#94a3b8",
  FOLLOWUP: "#38bdf8",
  HIGH_PRIORITY: "#f59e0b",
  ESCALATE: "#ef4444",
  CRITICAL: "#e11d48",
  DISPUTE_ROUTE: "#8b5cf6",
  RECONCILE: "#14b8a6",
  HANDOVER: "#a855f7",
};

function daysOverdue(dueDateIso) {
  const due = new Date(dueDateIso);
  const now = new Date();
  return Math.max(0, Math.floor((now - due) / (1000 * 60 * 60 * 24)));
}

function renderBadge(host, client, invoices) {
  const open = invoices.filter((inv) => inv.due_inr > 0);
  if (open.length === 0) return;

  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = `
    :host { all: initial; }
    .card {
      font-family: -apple-system, Segoe UI, Roboto, sans-serif;
      display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
      padding: 8px 12px; margin: 8px 0; border-radius: 8px;
      background: #12141b; border: 1px solid #232633; color: #e6e8ef; font-size: 13px;
    }
    .lamp { font-size: 14px; }
    .pill {
      display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px;
      border-radius: 999px; font-size: 11px; font-weight: 600; border: 1px solid currentColor;
    }
    .muted { color: #8b90a3; }
    a { color: #ff8a1f; text-decoration: none; font-weight: 600; cursor: pointer; }
  `;

  const card = document.createElement("div");
  card.className = "card";

  const primary = open[0];
  const decisionColor = DECISION_COLORS[primary.last_decision] || "#8b90a3";
  card.innerHTML = `
    <span class="lamp">🪔</span>
    <strong>${client.name}</strong>
    <span class="muted">${client.tier}</span>
    <span>${formatInr(primary.due_inr)} · ${daysOverdue(primary.due_date)} day(s) overdue</span>
    ${
      primary.last_decision
        ? `<span class="pill" style="color:${decisionColor}">${primary.last_decision}</span>`
        : ""
    }
    ${open.length > 1 ? `<span class="muted">+${open.length - 1} more invoice(s)</span>` : ""}
    <a data-role="why">Why?</a>
  `;

  const why = card.querySelector("[data-role='why']");
  why.addEventListener("click", () => {
    why.parentElement.insertAdjacentHTML(
      "beforeend",
      `<div class="muted" style="width:100%">${primary.number}: ${primary.state || "—"}${
        primary.last_severity != null ? ` · severity ${primary.last_severity}` : ""
      }</div>`,
    );
  });

  shadow.append(style, card);
}

async function scanForThread() {
  const injectionPoint = findInjectionPoint();
  if (!injectionPoint) return;
  if (injectionPoint.getAttribute(BADGE_MARK) === "done") return;

  const emails = currentParticipantEmails();
  if (emails.length === 0) return;

  for (const email of emails) {
    const response = await sendMessage({ type: "munimji:lookup", email });
    if (response?.ok && response.data?.client) {
      injectionPoint.setAttribute(BADGE_MARK, "done");
      const host = document.createElement("div");
      injectionPoint.insertAdjacentElement("afterend", host);
      renderBadge(host, response.data.client, response.data.invoices || []);
      return; // one badge per thread is enough, even if multiple clients matched
    }
  }
  // no participant matched a known client - mark as checked so we don't keep asking
  injectionPoint.setAttribute(BADGE_MARK, "done");
}

let debounceTimer = null;
function scheduleScan() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    scanForThread().catch(() => {}); // never let a lookup failure surface inside Gmail
  }, 400);
}

new MutationObserver(scheduleScan).observe(document.body, { childList: true, subtree: true });
scheduleScan();
