"""FastAPI server for T2URL.

Exposes the t2url library as a JSON API, persists each search (question -> URLs)
to SQLite, and serves the static web UI.

Run with:
    uvicorn server:app --reload
Then open http://127.0.0.1:8000/

Configuration (all optional, via environment variables):
    T2URL_RATE_LIMIT     Per-IP limit for /api/search   (default "20/minute").
    T2URL_ALLOW_ORIGINS  Comma-separated CORS origins
                         (default localhost dev origins; use "*" to allow all).
    T2URL_ADMIN_TOKEN    If set, the DELETE endpoints require this token in an
                         "X-Admin-Token" header. If unset, they stay open
                         (convenient for local single-user use).
"""

from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

# The t2url package lives under ./01_t2url (a numbered "src" dir whose name is
# not a valid Python identifier), so add it to the import path before importing.
sys.path.insert(0, str(Path(__file__).resolve().parent / "01_t2url"))

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from t2url import db, text_to_urls

# --- Rate limiting ----------------------------------------------------------
# Each web search can trigger an upstream DuckDuckGo call and (with augment) an
# LLM call, so throttle per client IP to keep the server and upstream quotas
# from being exhausted by rapid-fire requests.
RATE_LIMIT = os.environ.get("T2URL_RATE_LIMIT", "20/minute")
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="T2URL", description="Natural-language text -> URLs")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS -------------------------------------------------------------------
# Defaults to localhost dev origins. Override with T2URL_ALLOW_ORIGINS (a
# comma-separated list, or "*" to allow any origin) when deploying.
_origins_env = os.environ.get(
    "T2URL_ALLOW_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000",
)
ALLOW_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Admin guard for destructive endpoints ----------------------------------
ADMIN_TOKEN = os.environ.get("T2URL_ADMIN_TOKEN")


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Guard the DELETE endpoints when T2URL_ADMIN_TOKEN is configured.

    If no token is set the endpoints stay open (local single-user default);
    when a token is set, a matching ``X-Admin-Token`` header is required.
    """
    if ADMIN_TOKEN is None:
        return
    if not x_admin_token or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token.")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


class SearchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    max_results: int = Field(default=10, ge=1, le=50)
    augment: bool = False
    save: bool = True


class SavedSearch(BaseModel):
    id: int
    query: str
    augment: bool
    created_at: str
    urls: list[str]


class SearchResponse(BaseModel):
    id: int | None = None
    query: str
    urls: list[str]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
@limiter.limit(RATE_LIMIT)
def search(request: Request, req: SearchRequest) -> SearchResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Query text is empty.")

    try:
        urls = text_to_urls(
            text,
            max_results=req.max_results,
            augment=req.augment,
        )
    except RuntimeError as exc:
        # Raised by the augment path for missing package / API key.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # search/LLM provider failure
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}") from exc

    search_id: int | None = None
    if req.save and urls:
        search_id = db.save_search(text, urls, augment=req.augment)

    return SearchResponse(id=search_id, query=text, urls=urls)


@app.get("/api/searches", response_model=list[SavedSearch])
def searches(limit: int = 50) -> list[SavedSearch]:
    return [SavedSearch(**row) for row in db.list_searches(limit=limit)]


@app.delete("/api/searches/{search_id}", dependencies=[Depends(require_admin)])
def delete_search(search_id: int) -> dict[str, bool]:
    db.delete_search(search_id)
    return {"deleted": True}


@app.delete("/api/searches", dependencies=[Depends(require_admin)])
def clear_searches() -> dict[str, bool]:
    db.clear_all()
    return {"cleared": True}


# Serve the static UI from ./02_web at the root. Declared after the API routes
# so they keep priority over the catch-all static mount.
_WEB_DIR = Path(__file__).resolve().parent / "02_web"
app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
