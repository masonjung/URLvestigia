"""T2URL — turn natural-language text into a list of URLs via DuckDuckGo.

    from t2url import text_to_urls

    # plain search
    urls = text_to_urls("best python web scraping libraries")

    # LLM-augmented search (needs ANTHROPIC_API_KEY)
    urls = text_to_urls("how do I keep my houseplants alive in winter", augment=True)
"""

from .core import text_to_urls
from .search import search_urls

__all__ = ["text_to_urls", "search_urls"]
__version__ = "0.1.0"
