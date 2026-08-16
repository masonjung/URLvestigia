"""AI layer — unit tests for `retrieval/t2url.py`.

Every test stubs `DDGS`. These verify the contract T2URL guarantees about search
results, not whether a search engine is up.
"""

import pytest

import t2url


class FakeDDGS:
    """Stand-in for `ddgs.DDGS` that records how it was called."""

    last_call = None

    def __init__(self, results=None, raises=None):
        self._results = results if results is not None else []
        self._raises = raises

    def text(self, query, **kwargs):
        FakeDDGS.last_call = {"query": query, **kwargs}
        if self._raises:
            raise self._raises
        return self._results


@pytest.fixture
def patched(monkeypatch):
    """Install a FakeDDGS returning `results`, and hand back the recorded call."""

    def _install(results=None, raises=None):
        monkeypatch.setattr(t2url, "DDGS", lambda: FakeDDGS(results, raises))
        FakeDDGS.last_call = None
        return FakeDDGS

    return _install


def test_extracts_urls_in_rank_order(patched, fake_results):
    patched(fake_results)
    urls = t2url.text_to_urls("cloudera cdp")

    assert urls[0] == "https://www.cloudera.com/products/cdp.html?utm_source=search"
    assert urls[1] == "https://docs.cloudera.com/cdp/latest/index.html"


def test_accepts_legacy_url_key(patched, fake_results):
    """ddgs renamed its result key from `url` to `href`.

    Supporting both is what keeps a library upgrade from silently returning zero
    results — the failure mode that is indistinguishable from "no matches".
    """
    patched(fake_results)
    urls = t2url.text_to_urls("cloudera cdp")

    assert "https://blog.cloudera.com/iceberg-in-cdp/" in urls


def test_deduplicates_exact_repeats(patched, fake_results):
    patched(fake_results)
    urls = t2url.text_to_urls("cloudera cdp")

    assert len(urls) == len(set(urls))
    assert len(urls) == 4  # five results, one exact repeat


def test_empty_text_short_circuits(patched):
    """Blank input must not reach a search engine at all."""
    patched([{"href": "https://example.com"}])

    assert t2url.text_to_urls("   ") == []
    assert FakeDDGS.last_call is None


def test_query_is_stripped(patched):
    patched([])
    t2url.text_to_urls("  cloudera cdp  ")

    assert FakeDDGS.last_call["query"] == "cloudera cdp"


def test_no_results_returns_empty_list(patched):
    """A throttled engine returns nothing. That must be an empty list, not None."""
    patched(None)

    assert t2url.text_to_urls("anything") == []


def test_options_are_forwarded(patched):
    patched([])
    t2url.text_to_urls(
        "iceberg",
        max_results=25,
        region="kr-kr",
        safesearch="off",
        timelimit="w",
        backend="duckduckgo,yahoo",
    )

    call = FakeDDGS.last_call
    assert call["max_results"] == 25
    assert call["region"] == "kr-kr"
    assert call["safesearch"] == "off"
    assert call["timelimit"] == "w"
    assert call["backend"] == "duckduckgo,yahoo"


def test_empty_timelimit_normalises_to_none(patched):
    """The Serve layer sends "" for "any time"; ddgs expects None."""
    patched([])
    t2url.text_to_urls("iceberg", timelimit="")

    assert FakeDDGS.last_call["timelimit"] is None


def test_results_without_a_url_are_skipped(patched):
    patched([
        {"title": "no link here"},
        {"href": ""},
        {"href": "https://example.com/real"},
    ])

    assert t2url.text_to_urls("x") == ["https://example.com/real"]


def test_engine_failure_propagates(patched):
    """Retrieval does not swallow errors — `app/server.py` turns them into a
    visible message, which is only possible if they surface here."""
    patched(raises=RuntimeError("rate limited"))

    with pytest.raises(RuntimeError, match="rate limited"):
        t2url.text_to_urls("iceberg")
