"""t2url — natural-language text in, a list of URLs out, via free web search.

Free to run: no API keys, no accounts — searches go to the engines' public
pages through the ddgs metasearch library. Persistence lives in
03_Database/db.py; this module is search only.
"""

from ddgs import DDGS

# ddgs search options:
# region: locale like "us-en", "kr-kr"; "wt-wt" for worldwide.
# safesearch: "off", "moderate", or "on"
# timelimit: d, w, m, y. Defaults to None (any time).
# backend: which engine(s) to query — a single name or a comma-delimited list,
#             e.g. "duckduckgo" or "duckduckgo,yahoo,startpage,yandex"; with a list,
#             ddgs stops as soon as it has max_results, falling through on failures.
#             (ddgs also supports google, brave, mojeek, wikipedia, but they are
#             blocked or empty too often from this network to expose in the UI.)
# max_results: max number of results. If None, returns results only from the first response.


def text_to_urls(text, *, max_results=10, region="wt-wt", safesearch="moderate",
                 timelimit=None, backend="duckduckgo"):
    """Natural-language text -> result URLs, deduplicated, in rank order."""
    text = text.strip()
    if not text:
        return []
    results = DDGS().text(
        text,
        region=region,
        safesearch=safesearch,
        timelimit=timelimit or None,
        backend=backend,
        max_results=max_results,
    )
    urls = []
    for item in results or []:
        url = item.get("href") or item.get("url")  # ddgs renamed "url" to "href"
        if url and url not in urls:
            urls.append(url)
    return urls
