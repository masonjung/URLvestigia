"""urlvestigia — natural-language text in, a list of URLs out, via free web search.

Free to run: no API keys, no accounts. Web searches go to the engines' public pages
through the ddgs metasearch library; Wikipedia, OpenAlex, and arXiv are reached
through their own keyless APIs in providers.py. Persistence lives in data/db.py;
this module is search only.

One search uses one provider. Within `ddgs`, `backend` is still a fallback chain —
engines tried in order until `max_results` is filled. Across providers there is no
chain, because they are different corpora: falling through from a web engine to
arXiv would answer a web-search miss with physics preprints.
"""

from ddgs import DDGS
from ddgs.exceptions import DDGSException

import providers
from providers import SUPPORTS

# ddgs search options:
# region: locale like "us-en", "kr-kr"; "wt-wt" for worldwide.
# safesearch: "off", "moderate", or "on"
# timelimit: d, w, m, y. Defaults to None (any time).
# backend: which engine(s) to query — a single name or a comma-delimited list,
#             e.g. "duckduckgo" or "duckduckgo,yahoo,startpage,yandex"; with a list,
#             ddgs stops as soon as it has max_results, falling through on failures.
#             (ddgs also supports google, brave, mojeek, wikipedia, but they are
#             blocked or empty too often from this network to expose in the UI.
#             Wikipedia is exposed as its own provider instead, via the MediaWiki
#             API, because the ddgs backend cannot map a region to a language.)
# max_results: max number of results. If None, returns results only from the first response.

DEFAULT_PROVIDER = "ddgs"

# ddgs signals "every engine answered, none had anything" by raising rather than
# returning an empty list, with this exact message. Matching on the string is
# unlovely, but it is the only signal the library exposes: the alternative is
# reporting an ordinary empty result set to the user as a hard error, in red, next
# to the app's own "No results found." saying the opposite. If a future ddgs
# reworded it, this stops matching and the behaviour reverts to what it is today.
_DDGS_EMPTY = "No results found."


def _search_ddgs(text, *, max_results, region="wt-wt", safesearch="moderate",
                 timelimit=None, backend="duckduckgo"):
    """Web results through the ddgs metasearch library.

    An empty result comes back as `[]`. A genuine failure — rate limited, blocked,
    transport error — is left to propagate, because those the caller must report.
    """
    try:
        results = DDGS().text(
            text,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit or None,
            backend=backend,
            max_results=max_results,
        )
    except DDGSException as exc:
        if str(exc) == _DDGS_EMPTY:
            return []
        raise
    # ddgs renamed "url" to "href"; accept either so a library upgrade cannot
    # silently return zero results.
    return [item.get("href") or item.get("url") for item in results or []]


# Provider id -> search function. ddgs is a library call and stays here; the HTTP
# providers live in providers.py.
REGISTRY = {DEFAULT_PROVIDER: _search_ddgs, **providers.REGISTRY}


def supports(provider):
    """The option names `provider` actually applies.

    Callers use this to avoid recording an option that was never applied. A
    Wikipedia search stamped `timelimit="w"` would be a false claim in a governed
    table, and the whole point of persisting the options is that a search can be
    reproduced from them.
    """
    return SUPPORTS.get(provider, frozenset())


def text_to_urls(text, *, provider=DEFAULT_PROVIDER, max_results=10, region="wt-wt",
                 safesearch="moderate", timelimit=None, backend="duckduckgo"):
    """Natural-language text -> result URLs, deduplicated, in rank order.

    Options a provider does not support are dropped rather than passed and ignored,
    so a provider can never be handed a filter it would silently discard.
    """
    text = text.strip()
    if not text:
        return []

    search = REGISTRY.get(provider) or REGISTRY[DEFAULT_PROVIDER]
    options = {
        "region": region,
        "safesearch": safesearch,
        "timelimit": timelimit or None,
        "backend": backend,
    }
    applied = {name: value for name, value in options.items()
               if name in supports(provider)}

    urls = []
    for url in search(text, max_results=max_results, **applied) or []:
        if url and url not in urls:
            urls.append(url)
    # ddgs enforces its own ceiling; the API providers are asked for max_results but
    # the cap is re-applied here so the guarantee holds however a provider behaves.
    return urls[:max_results]
