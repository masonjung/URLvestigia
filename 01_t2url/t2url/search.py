"""Plain DuckDuckGo search — natural-language text in, result URLs out."""

from __future__ import annotations

from ddgs import DDGS


def search_urls(
    query: str,
    *,
    max_results: int = 10,
    region: str = "wt-wt",
    safesearch: str = "moderate",
) -> list[str]:
    """Run a single query against DuckDuckGo and return result URLs.

    Args:
        query: The search query (plain text).
        max_results: Maximum number of URLs to return.
        region: DuckDuckGo region code, e.g. ``"wt-wt"`` (no region), ``"us-en"``.
        safesearch: ``"on"``, ``"moderate"``, or ``"off"``.

    Returns:
        A list of result URLs, in DuckDuckGo's ranking order, deduplicated.
    """
    query = query.strip()
    if not query:
        return []

    results = DDGS().text(
        query,
        region=region,
        safesearch=safesearch,
        max_results=max_results,
    )

    urls: list[str] = []
    seen: set[str] = set()
    for item in results or []:
        # `ddgs` returns "href"; older clients used "url" — accept either.
        url = item.get("href") or item.get("url")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls
