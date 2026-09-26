function sendMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => resolve(response));
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

async function render() {
  const content = document.getElementById("content");
  const response = await sendMessage({ type: "munimji:approvals" });

  if (!response?.ok) {
    content.innerHTML = `Backend not reachable. Check <a id="fix" href="#">settings</a>.`;
    document.getElementById("fix")?.addEventListener("click", (e) => {
      e.preventDefault();
      chrome.runtime.openOptionsPage();
    });
    return;
  }

  const rows = response.data;
  if (rows.length === 0) {
    content.textContent = "Nothing parked right now.";
    return;
  }

  content.innerHTML = "";
  for (const row of rows) {
    let payload = {};
    try {
      payload = JSON.parse(row.payload_json || "{}");
    } catch {
      payload = {};
    }

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="row">
        <span class="muted">${escapeHtml(row.action_type)}</span>
        <span class="muted">${escapeHtml(payload.to || "")}</span>
      </div>
      ${payload.subject ? `<div class="subject">${escapeHtml(payload.subject)}</div>` : ""}
      ${payload.body ? `<div class="body">${escapeHtml(payload.body)}</div>` : ""}
      <div class="actions">
        <button class="approve" data-action="approve">✅ Approve</button>
        <button class="reject" data-action="reject">❌ Reject</button>
      </div>
    `;

    card.querySelector("[data-action='approve']").addEventListener("click", async (e) => {
      e.target.disabled = true;
      await sendMessage({ type: "munimji:approve", idemKey: row.idem_key });
      render();
    });
    card.querySelector("[data-action='reject']").addEventListener("click", async (e) => {
      e.target.disabled = true;
      await sendMessage({ type: "munimji:reject", idemKey: row.idem_key });
      render();
    });

    content.appendChild(card);
  }
}

document.getElementById("options-link").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

render();
