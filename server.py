"""FastAPI server for T2URL.

Exposes the t2url library as a JSON API, persists each search (question -> URLs)
to SQLite, and serves the static web UI.

Run with:
    uvicorn server:app --reload
Then open http://127.0.0.1:8000/
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from t2url import db, text_to_urls

app = FastAPI(title="T2URL", description="Natural-language text -> URLs")

# Permissive CORS so you can also open the page from a separate dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


class SearchRequest(BaseModel):
    text: str
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
def search(req: SearchRequest) -> SearchResponse:
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


@app.delete("/api/searches/{search_id}")
def delete_search(search_id: int) -> dict[str, bool]:
    db.delete_search(search_id)
    return {"deleted": True}


@app.delete("/api/searches")
def clear_searches() -> dict[str, bool]:
    db.clear_all()
    return {"cleared": True}


# Serve the static UI from /web at the root. Declared after the API routes so
# they keep priority over the catch-all static mount.
app.mount("/", StaticFiles(directory="web", html=True), name="web")
