"""SQLite persistence for searches: each (question -> URLs) pair is stored
relationally so it can be queried from any SQL tooling.

Schema
------
searches(id, query, augment, created_at)
search_urls(id, search_id -> searches.id, position, url)

A search has many URLs (one row per URL, ordered by ``position``), so the data
is fully normalized rather than a blob of JSON.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "t2url.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS searches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    query      TEXT    NOT NULL,
    augment    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS search_urls (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER NOT NULL,
    position  INTEGER NOT NULL,
    url       TEXT    NOT NULL,
    FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_search_urls_search_id ON search_urls(search_id);
"""


def _connect(path: str | Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | Path | None = None) -> None:
    """Create tables if they don't exist. Safe to call repeatedly."""
    with _connect(path) as conn:
        conn.executescript(_SCHEMA)


def save_search(
    query: str,
    urls: list[str],
    *,
    augment: bool = False,
    path: str | Path | None = None,
) -> int:
    """Insert a search and its URLs; return the new search id."""
    created = datetime.now(timezone.utc).isoformat()
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO searches (query, augment, created_at) VALUES (?, ?, ?)",
            (query, int(augment), created),
        )
        search_id = int(cur.lastrowid)
        conn.executemany(
            "INSERT INTO search_urls (search_id, position, url) VALUES (?, ?, ?)",
            [(search_id, i, url) for i, url in enumerate(urls)],
        )
    return search_id


def list_searches(
    limit: int = 50,
    *,
    path: str | Path | None = None,
) -> list[dict]:
    """Return recent searches (newest first), each with its ordered URLs."""
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id, query, augment, created_at FROM searches "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        out: list[dict] = []
        for r in rows:
            urls = conn.execute(
                "SELECT url FROM search_urls WHERE search_id = ? "
                "ORDER BY position",
                (r["id"],),
            ).fetchall()
            out.append(
                {
                    "id": r["id"],
                    "query": r["query"],
                    "augment": bool(r["augment"]),
                    "created_at": r["created_at"],
                    "urls": [u["url"] for u in urls],
                }
            )
    return out


def delete_search(search_id: int, *, path: str | Path | None = None) -> None:
    """Delete one search (its URLs cascade away)."""
    with _connect(path) as conn:
        conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))


def clear_all(*, path: str | Path | None = None) -> None:
    """Delete every saved search."""
    with _connect(path) as conn:
        conn.execute("DELETE FROM search_urls")
        conn.execute("DELETE FROM searches")
