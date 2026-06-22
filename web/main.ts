// Frontend logic for T2URL: run a search, then render the saved-searches
// table (question -> URLs) from the SQL-backed history endpoint.

interface SearchResponse {
  id: number | null;
  query: string;
  urls: string[];
}

interface SavedSearch {
  id: number;
  query: string;
  augment: boolean;
  created_at: string;
  urls: string[];
}

const form = document.getElementById("search-form") as HTMLFormElement;
const textEl = document.getElementById("text") as HTMLTextAreaElement;
const maxResultsEl = document.getElementById("max_results") as HTMLInputElement;
const augmentEl = document.getElementById("augment") as HTMLInputElement;
const submitEl = document.getElementById("submit") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLParagraphElement;
const historyBody = document.getElementById("history-body") as HTMLTableSectionElement;
const clearAllEl = document.getElementById("clear-all") as HTMLButtonElement;

async function search(): Promise<void> {
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

    const data: SearchResponse = await res.json();
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

async function errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // non-JSON body
  }
  return `${res.status} ${res.statusText}`;
}

async function loadHistory(): Promise<void> {
  const res = await fetch("/api/searches");
  if (!res.ok) return;
  const rows: SavedSearch[] = await res.json();
  renderHistory(rows);
}

function renderHistory(rows: SavedSearch[]): void {
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

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function deleteRow(id: number): Promise<void> {
  await fetch(`/api/searches/${id}`, { method: "DELETE" });
  await loadHistory();
}

async function clearAll(): Promise<void> {
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
