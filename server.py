"""T2URL web app — everything is rendered server-side, no JavaScript.

Run:  uvicorn server:app --reload   then open http://127.0.0.1:8000/
"""

import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "01_t2url"))
sys.path.insert(0, str(ROOT / "03_Database"))

import db
import t2url
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="T2URL")
templates = Jinja2Templates(directory=str(ROOT / "02_web"))
db.init_db()

# Allowed values per search option; first entry is the default fallback.
OPTIONS = {
    "timelimit": ["", "d", "w", "m", "y"],
    "backend": ["duckduckgo", "google", "brave", "yahoo",
                "mojeek", "startpage", "wikipedia", "yandex"],
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
    return templates.TemplateResponse(request, "index.html", {"rows": rows, "msg": msg})


@app.post("/search")
def search(
    text: str = Form(...),
    max_results: int = Form(10),
    timelimit: str = Form(""),
    backend: str = Form("duckduckgo"),
    safesearch: str = Form("moderate"),
    region: str = Form("wt-wt"),
):
    text = text.strip()
    if not text:
        return _redirect()
    timelimit = _pick("timelimit", timelimit)
    backend = _pick("backend", backend)
    safesearch = _pick("safesearch", safesearch)
    region = _pick("region", region)
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
