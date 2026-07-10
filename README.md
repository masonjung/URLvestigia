# T2URL

Turn natural-language text into a list of URLs using free web search
(DuckDuckGo by default; Google, Brave, Yahoo and more via the `ddgs`
metasearch library).

Free to run: no API keys, no accounts, no build step. The only external
services it talks to are the search engines' public pages.

## Install & run

```bash
pip install -r requirements.txt
uvicorn server:app --reload
# open http://127.0.0.1:8000/
```

Type a request, pick your options (time range, search engine, region,
safesearch, max results), and you get a clickable list of URLs. The UI is
plain HTML and CSS rendered by the server — no JavaScript.

## Storage

The database is **SQLite**, a single file at `03_Database/t2url.db`
(set the `T2URL_DB` env var to move it). The schema lives in
`03_Database/schema.sql` and all SQL goes through `03_Database/db.py`.
Every search is saved with the
options that produced it, and the table below the form shows each one —
query, time, engine, region, safesearch, max — alongside its URLs. Only
links are stored, never page content. The **Dedupe URLs** button above the
table permanently deletes duplicate URLs across searches, keeping the
earliest occurrence.

## Library

```python
from t2url import text_to_urls

urls = text_to_urls("best python web scraping libraries", max_results=10)
```

Options: `max_results` (10), `region` (`"wt-wt"`, e.g. `"us-en"`, `"kr-kr"`),
`safesearch` (`"on"` / `"moderate"` / `"off"`), `timelimit` (`None`, `"d"`,
`"w"`, `"m"`, `"y"`), and `backend` (`"duckduckgo"` by default, or `"google"`,
`"brave"`, `"yahoo"`, `"mojeek"`, `"startpage"`, `"wikipedia"`, `"yandex"`).
URLs come back deduplicated in ranking order.

## Layout

```
01_t2url/t2url.py       the library: text -> URLs via web search
02_web/index.html       the UI, a Jinja2 template (HTML + CSS only)
03_Database/db.py       sqlite persistence: all SQL lives here
03_Database/schema.sql  the schema (tables + index)
03_Database/t2url.db    the database itself (gitignored)
server.py               FastAPI app: renders the page, handles form posts
```

The numbered directories act as "src" directories: `server.py` and
`example.py` add them to the import path so `from t2url import ...` and
`import db` work.
