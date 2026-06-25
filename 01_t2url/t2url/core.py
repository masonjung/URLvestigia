"""Main entry point: natural-language text -> list of URLs."""

from __future__ import annotations

from .search import search_urls


def text_to_urls(
    text: str,
    *,
    max_results: int = 10,
    augment: bool = False,
    max_queries: int = 3,
    region: str = "wt-wt",
    safesearch: str = "moderate",
    model: str = "claude-opus-4-8",
    client=None,
) -> list[str]:
    """Convert a natural-language request into a list of result URLs.

    By default this performs a plain DuckDuckGo search using ``text`` as the
    query. With ``augment=True``, Claude first expands ``text`` into several
    focused search queries; each is searched and the results are merged
    (deduplicated, original order preserved) up to ``max_results``.

    Args:
        text: The user's natural-language input.
        max_results: Maximum number of URLs to return overall.
        augment: If ``True``, use the LLM to refine the query first.
        max_queries: When augmenting, the max number of queries to generate.
        region: DuckDuckGo region code (e.g. ``"wt-wt"``, ``"us-en"``).
        safesearch: ``"on"``, ``"moderate"``, or ``"off"``.
        model: Anthropic model ID (only used when ``augment=True``).
        client: Optional ``anthropic.Anthropic`` instance for augmentation.

    Returns:
        A list of result URLs.
    """
    if not augment:
        return search_urls(
            text,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
        )

    # Lazy import so plain search never requires the anthropic package.
    from .augment import expand_queries

    queries = expand_queries(
        text,
        max_queries=max_queries,
        model=model,
        client=client,
    )

    urls: list[str] = []
    seen: set[str] = set()
    for query in queries:
        for url in search_urls(
            query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
        ):
            if url not in seen:
                seen.add(url)
                urls.append(url)
                if len(urls) >= max_results:
                    return urls
    return urls
