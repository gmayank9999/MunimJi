const apiBaseInput = document.getElementById("apiBase");
const extKeyInput = document.getElementById("extKey");
const status = document.getElementById("status");

chrome.storage.sync.get(["apiBase", "extKey"], (stored) => {
  apiBaseInput.value = stored.apiBase || "http://localhost:8000";
  extKeyInput.value = stored.extKey || "";
});

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.sync.set(
    { apiBase: apiBaseInput.value.trim(), extKey: extKeyInput.value.trim() },
    () => {
      status.textContent = "Saved.";
      setTimeout(() => (status.textContent = ""), 2000);
    },
  );
});
