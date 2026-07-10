"""T2URL persistence — SQLite storage for searches and their result URLs.

The database is a single SQLite file, `t2url.db` in this directory by default
(set the T2URL_DB env var to move it). The schema lives in schema.sql.
Only links are stored, never page content.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("T2URL_DB") or HERE / "t2url.db")

_SCHEMA = (HERE / "schema.sql").read_text(encoding="utf-8")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _db() as conn:
        conn.executescript(_SCHEMA)
        # Migrate DBs created before the settings columns existed.
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(searches)")}
        for col, sqltype in (("region", "TEXT"), ("safesearch", "TEXT"), ("timelimit", "TEXT"),
                             ("backend", "TEXT"), ("max_results", "INTEGER")):
            if col not in cols:
                conn.execute(f"ALTER TABLE searches ADD COLUMN {col} {sqltype}")


def save_search(query, urls, *, region=None, safesearch=None, timelimit=None,
                backend=None, max_results=None):
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO searches"
            " (query, created_at, region, safesearch, timelimit, backend, max_results)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (query, datetime.now(timezone.utc).isoformat(),
             region, safesearch, timelimit, backend, max_results),
        )
        conn.executemany(
            "INSERT INTO search_urls (search_id, position, url) VALUES (?, ?, ?)",
            [(cur.lastrowid, i, url) for i, url in enumerate(urls)],
        )
        return cur.lastrowid


def list_searches(limit=50):
    """Recent searches, newest first, each with its ordered URLs."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, query, created_at, region, safesearch, timelimit, backend, max_results"
            " FROM searches ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{
            "id": r["id"],
            "query": r["query"],
            "created_at": r["created_at"],
            "region": r["region"],
            "safesearch": r["safesearch"],
            "timelimit": r["timelimit"],
            "backend": r["backend"],
            "max_results": r["max_results"],
            "urls": [u["url"] for u in conn.execute(
                "SELECT url FROM search_urls WHERE search_id = ? ORDER BY position", (r["id"],)
            )],
        } for r in rows]


def delete_search(search_id):
    with _db() as conn:
        conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))


def clear_all():
    with _db() as conn:
        conn.execute("DELETE FROM search_urls")
        conn.execute("DELETE FROM searches")


def dedupe_urls():
    """Delete duplicate URLs across searches, keeping the earliest occurrence.

    Searches left with no URLs are removed too. Returns the number of URL rows deleted.
    """
    with _db() as conn:
        cur = conn.execute(
            "DELETE FROM search_urls WHERE id NOT IN"
            " (SELECT MIN(id) FROM search_urls GROUP BY url)"
        )
        conn.execute(
            "DELETE FROM searches WHERE id NOT IN (SELECT DISTINCT search_id FROM search_urls)"
        )
        return cur.rowcount
