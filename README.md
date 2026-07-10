# T2URL

Turn natural-language text into a list of URLs using free web search
(DuckDuckGo by default; Yahoo, Startpage, and Yandex via the `ddgs`
metasearch library).

Free to run: no API keys, no accounts, no build step. The only external
services it talks to are the search engines' public pages.

## Install & run

```bash
pip install -r requirements.txt
uvicorn server:app --reload
# open http://127.0.0.1:8000/
```

Type a request, pick your options (time range, engines, region, safesearch,
max results), and you get a clickable list of URLs. Engines are toggle
buttons — DuckDuckGo is on by default; click to activate more (a throttled
engine then falls through to the next) or deactivate any of them. If none
are active the search uses DuckDuckGo; the saved table shows `any` when all
four were used. The UI is plain HTML and CSS rendered by the server — no
JavaScript.

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
`"w"`, `"m"`, `"y"`), and `backend` — a single engine or a comma-delimited
list (`"duckduckgo"`, `"yahoo"`, `"startpage"`, `"yandex"`, e.g.
`"duckduckgo,yahoo"`); with a list, engines are tried until enough results
arrive, so one throttled engine doesn't fail the search. ddgs also supports
google, brave, mojeek, and wikipedia, but they are blocked or empty too often
to be exposed in the UI. URLs come back deduplicated in ranking order.

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
