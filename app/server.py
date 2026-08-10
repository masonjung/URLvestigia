"""T2URL Serve layer — everything is rendered server-side, no JavaScript.

Run:  make dev   (or: uvicorn app.server:app --reload)
then open http://127.0.0.1:8000/
"""

import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "data"))

import db
import t2url
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Webdig")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
db.init_db()

# Allowed values per search option; first entry is the default fallback.
OPTIONS = {
    "provider": ["ddgs", "wikipedia", "openalex", "arxiv"],
    "timelimit": ["", "d", "w", "m", "y"],
    "backend": ["duckduckgo", "yahoo", "startpage", "yandex"],
    "safesearch": ["moderate", "off", "on"],
    "region": ["wt-wt", "us-en", "uk-en", "kr-kr", "jp-jp", "de-de", "fr-fr"],
}

PROVIDER_LABELS = {
    "ddgs": "Web",
    "wikipedia": "Wikipedia",
    "openalex": "OpenAlex",
    "arxiv": "arXiv",
}

# The per-search options a provider might not apply. `backend` is in here with the
# rest: the engine chain is just another control that only one provider supports.
TOGGLEABLE = ("region", "safesearch", "timelimit", "backend")


def _pick(name, value):
    allowed = OPTIONS[name]
    return value if value in allowed else allowed[0]


def _providers():
    """Provider id, label, and the options it does not apply.

    The template renders its radio pills and emits its control-visibility CSS from
    this, so the support matrix in ai/providers.py is never restated in markup
    where it could drift out of step with what the server enforces.
    """
    return [{
        "id": name,
        "label": PROVIDER_LABELS.get(name, name),
        "unsupported": [opt for opt in TOGGLEABLE
                        if opt not in t2url.supports(name)],
    } for name in OPTIONS["provider"]]


def _redirect(msg=""):
    return RedirectResponse(f"/?msg={quote(msg)}" if msg else "/", status_code=303)


def _when(iso):
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%b %d %H:%M")
    except ValueError:
        return iso


@app.get("/")
def home(request: Request, msg: str = ""):
    rows = db.list_searches()
    for r in rows:
        r["when"] = _when(r["created_at"])
        # Always the engines as stored, never a summary. A full selection used to
        # render as "any", which was wrong three ways: it hid which engines were
        # asked, it read as the Time column's "any" (no time limit) in the
        # neighbouring cell, and because the test compared against the *current*
        # engine list, adding one silently re-labelled historical rows.
        r["backend_label"] = (r["backend"] or "").replace(",", "+") or None
        r["provider_label"] = PROVIDER_LABELS.get(r["provider"], r["provider"])
    try:
        db_label = db.DB_PATH.relative_to(ROOT).as_posix()
    except ValueError:
        db_label = str(db.DB_PATH)
    return templates.TemplateResponse(request, "index.html", {
        "rows": rows, "msg": msg, "stats": db.stats(), "db_label": db_label,
        "providers": _providers(),
    })


@app.post("/search")
def search(
    text: str = Form(...),
    provider: str = Form("ddgs"),
    max_results: int = Form(10),
    timelimit: str = Form(""),
    backend: list[str] = Form([]),
    safesearch: str = Form("moderate"),
    region: str = Form("wt-wt"),
):
    text = text.strip()
    if not text:
        return _redirect()
    provider = _pick("provider", provider)
    timelimit = _pick("timelimit", timelimit)
    safesearch = _pick("safesearch", safesearch)
    region = _pick("region", region)
    # Checked engines, whitelist-filtered and deduped; none checked means the default engine.
    engines = [b for b in dict.fromkeys(backend) if b in OPTIONS["backend"]]
    backend = ",".join(engines or ["duckduckgo"])
    max_results = min(max(max_results, 1), 50)
    try:
        # Every option is passed; text_to_urls drops the ones this provider does
        # not apply, reading the same matrix used below.
        urls = t2url.text_to_urls(
            text,
            provider=provider,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit or None,
            backend=backend,
        )
    except Exception as exc:
        return _redirect(f"Error: {exc}")
    if not urls:
        return _redirect("No results found.")
    # Record only what this provider actually applied. An unsupported option is
    # stored NULL rather than as the value the form happened to post — a Wikipedia
    # search stamped timelimit="w" would claim a filter that never ran.
    supported = t2url.supports(provider)
    chosen = {"region": region, "safesearch": safesearch,
              "timelimit": timelimit, "backend": backend}
    db.save_search(
        text, urls, provider=provider, max_results=max_results,
        **{name: (value if name in supported else None)
           for name, value in chosen.items()},
    )
    return _redirect(f'{len(urls)} result{"" if len(urls) == 1 else "s"} saved for "{text}"')


@app.post("/delete/{search_id}")
def delete(search_id: int):
    db.delete_search(search_id)
    return _redirect()


@app.post("/dedupe")
def dedupe():
    removed = db.dedupe_urls()
    if not removed:
        return _redirect("No duplicate URLs found.")
    return _redirect(f'Removed {removed} duplicate URL{"" if removed == 1 else "s"}.')


@app.post("/clear")
def clear():
    db.clear_all()
    return _redirect()
