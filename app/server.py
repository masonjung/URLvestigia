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
    "timelimit": ["", "d", "w", "m", "y"],
    "backend": ["duckduckgo", "yahoo", "startpage", "yandex"],
    "safesearch": ["moderate", "off", "on"],
    "region": ["wt-wt", "us-en", "uk-en", "kr-kr", "jp-jp", "de-de", "fr-fr"],
}


def _pick(name, value):
    allowed = OPTIONS[name]
    return value if value in allowed else allowed[0]


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
        if r["backend"] and set(r["backend"].split(",")) == set(OPTIONS["backend"]):
            r["backend_label"] = "any"
        else:
            r["backend_label"] = (r["backend"] or "").replace(",", "+") or None
    try:
        db_label = db.DB_PATH.relative_to(ROOT).as_posix()
    except ValueError:
        db_label = str(db.DB_PATH)
    return templates.TemplateResponse(request, "index.html", {
        "rows": rows, "msg": msg, "stats": db.stats(), "db_label": db_label,
    })


@app.post("/search")
def search(
    text: str = Form(...),
    max_results: int = Form(10),
    timelimit: str = Form(""),
    backend: list[str] = Form([]),
    safesearch: str = Form("moderate"),
    region: str = Form("wt-wt"),
):
    text = text.strip()
    if not text:
        return _redirect()
    timelimit = _pick("timelimit", timelimit)
    safesearch = _pick("safesearch", safesearch)
    region = _pick("region", region)
    # Checked engines, whitelist-filtered and deduped; none checked means the default engine.
    engines = [b for b in dict.fromkeys(backend) if b in OPTIONS["backend"]]
    backend = ",".join(engines or ["duckduckgo"])
    max_results = min(max(max_results, 1), 50)
    try:
        urls = t2url.text_to_urls(
            text,
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
    db.save_search(text, urls, region=region, safesearch=safesearch,
                   timelimit=timelimit or None, backend=backend, max_results=max_results)
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
