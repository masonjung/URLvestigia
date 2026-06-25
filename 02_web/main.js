// Compiled from main.ts (types stripped). Recompile with `npm run build`
// if you change main.ts and have Node/TypeScript installed.

const form = document.getElementById("search-form");
const textEl = document.getElementById("text");
const maxResultsEl = document.getElementById("max_results");
const augmentEl = document.getElementById("augment");
const submitEl = document.getElementById("submit");
const statusEl = document.getElementById("status");
const historyBody = document.getElementById("history-body");
const clearAllEl = document.getElementById("clear-all");

async function search() {
  const text = textEl.value.trim();
  if (!text) return;

  submitEl.disabled = true;
  statusEl.textContent = "Searching…";

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        max_results: Number(maxResultsEl.value) || 10,
        augment: augmentEl.checked,
      }),
    });

    if (!res.ok) {
      throw new Error(await errorDetail(res));
    }

    const data = await res.json();
    statusEl.textContent =
      data.urls.length === 0
        ? "No results found."
        : `${data.urls.length} result${data.urls.length === 1 ? "" : "s"} saved for "${data.query}"`;
    await loadHistory();
  } catch (err) {
    statusEl.textContent = `Error: ${err instanceof Error ? err.message : String(err)}`;
  } finally {
    submitEl.disabled = false;
  }
}

async function errorDetail(res) {
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // non-JSON body
  }
  return `${res.status} ${res.statusText}`;
}

async function loadHistory() {
  const res = await fetch("/api/searches");
  if (!res.ok) return;
  const rows = await res.json();
  renderHistory(rows);
}

function renderHistory(rows) {
  historyBody.replaceChildren();

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.className = "empty";
    td.textContent = "// no searches yet — run one above";
    tr.appendChild(td);
    historyBody.appendChild(tr);
    return;
  }

  for (const row of rows) {
    const tr = document.createElement("tr");

    const idCell = document.createElement("td");
    idCell.className = "col-id";
    idCell.textContent = String(row.id);
    tr.appendChild(idCell);

    const qCell = document.createElement("td");
    qCell.className = "col-q";
    qCell.textContent = row.query;
    if (row.augment) {
      const badge = document.createElement("span");
      badge.className = "badge-ai";
      badge.textContent = "AI";
      qCell.appendChild(badge);
    }
    tr.appendChild(qCell);

    const urlCell = document.createElement("td");
    const list = document.createElement("div");
    list.className = "url-list";
    for (const url of row.urls) {
      const a = document.createElement("a");
      a.href = url;
      a.textContent = url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      list.appendChild(a);
    }
    urlCell.appendChild(list);
    tr.appendChild(urlCell);

    const whenCell = document.createElement("td");
    whenCell.className = "col-when";
    whenCell.textContent = formatWhen(row.created_at);
    tr.appendChild(whenCell);

    const delCell = document.createElement("td");
    const del = document.createElement("button");
    del.className = "row-del";
    del.title = "Delete";
    del.textContent = "✕";
    del.addEventListener("click", () => void deleteRow(row.id));
    delCell.appendChild(del);
    tr.appendChild(delCell);

    historyBody.appendChild(tr);
  }
}

function formatWhen(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function deleteRow(id) {
  await fetch(`/api/searches/${id}`, { method: "DELETE" });
  await loadHistory();
}

async function clearAll() {
  if (!confirm("Delete all saved searches?")) return;
  await fetch("/api/searches", { method: "DELETE" });
  await loadHistory();
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  void search();
});
clearAllEl.addEventListener("click", () => void clearAll());

void loadHistory();
