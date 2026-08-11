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

import backup
import db
import t2url
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="URLoom")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
db.init_db()

# Allowed values per search option; first entry is the default fallback.
#
# `provider` is the list the UI offers, which is a subset of what ai/ implements —
# openalex is still a working provider in t2url.REGISTRY, it is simply not on the
# form. Anything not listed here is coerced back to the default by _pick(), so a
# provider withdrawn from the UI cannot be reached by posting it by hand either.
OPTIONS = {
    "provider": ["ddgs", "wikipedia", "arxiv"],
    "timelimit": ["", "d", "w", "m", "y"],
    "backend": ["duckduckgo", "yahoo", "startpage", "yandex"],
    "safesearch": ["moderate", "off", "on"],
    "region": ["wt-wt", "us-en", "uk-en", "kr-kr", "jp-jp", "de-de", "fr-fr"],
}

# Labels for every provider that has ever been searched, not just the ones on offer:
# `home()` reads this to render the Provider column, so dropping a retired provider's
# label here would relabel its historical rows with the bare id.
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


def _rel(path):
    """Repo-relative when the path is inside the repo, absolute when it is not.

    `T2URL_DB` and `T2URL_BACKUP_DIR` can both point anywhere, so neither label
    can assume it is showing something under ROOT.
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


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
    return templates.TemplateResponse(request, "index.html", {
        "rows": rows, "msg": msg, "stats": db.stats(),
        "db_label": _rel(db.DB_PATH), "providers": _providers(),
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
    # Checked engines, whitelist-filtered and deduped. None checked means all of them,
    # not one of them — for resilience, not coverage. Selecting more engines is *not*
    # free extra results: ddgs queries them concurrently and drops the ones that miss
    # its first wait(), so a wider selection can return fewer URLs than the best single
    # engine (see "Multi-engine is resilience" in docs/ARCHITECTURE.md). What it buys
    # is that one blocked engine no longer empties the search, and that is the failure
    # actually being seen — duckduckgo alone returned nothing on every attempt from
    # this network while all four returned results on every attempt.
    engines = [b for b in dict.fromkeys(backend) if b in OPTIONS["backend"]]
    backend = ",".join(engines or OPTIONS["backend"])
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
        # Name what failed. The exception text comes from whichever library made the
        # call and says nothing about which corpus was searched or, for a chain of
        # four engines, which of them was asked — so the bare message left the user
        # unable to tell a blocked engine from a broken query.
        where = PROVIDER_LABELS.get(provider, provider)
        if provider == "ddgs":
            where += f" ({backend.replace(',', ' + ')})"
        return _redirect(f"Error: {where} search failed — {exc}")
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


@app.post("/store")
def store():
    """Write a dated snapshot of the dev store to the local backups directory.

    Safe to press while searches are running — `db.backup()` uses SQLite's online
    backup API, not a file copy. Nothing here overwrites: a snapshot is only ever
    added, which is why this sits next to the destructive Clear all without
    needing a confirmation of its own.
    """
    try:
        written = backup.snapshot()
    except FileExistsError:
        # Two presses inside one second. Names are second-resolution, so the
        # second press genuinely stored nothing and must not report success.
        return _redirect("Error: a snapshot for this second already exists — "
                         "wait a moment and press Store again.")
    except Exception as exc:
        return _redirect(f"Error: backup failed — {exc}")
    # Counted out of the finished file rather than the live store: it proves the
    # snapshot opens as a database, which is the only part of "it worked" a
    # backup can meaningfully claim.
    rows = backup.counts(written)
    return _redirect(f"Stored {_rel(written)} — {rows['searches']} searches, "
                     f"{rows['search_urls']} URLs.")


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
