-- T2URL schema: one row per search in `searches`, one row per URL in `search_urls`.
CREATE TABLE IF NOT EXISTS searches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query       TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    region      TEXT,
    safesearch  TEXT,
    timelimit   TEXT,
    backend     TEXT,
    max_results INTEGER
);
CREATE TABLE IF NOT EXISTS search_urls (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    url       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_urls_search_id ON search_urls(search_id);
