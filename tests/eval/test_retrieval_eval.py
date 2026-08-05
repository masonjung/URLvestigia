"""AI eval harness — the Harden gate for `ai/t2url.py`.

Two tiers:

* **Contract tests** (always run) assert the guarantees every caller depends on,
  against a stubbed engine. Fast, deterministic, safe in CI.
* **Live tests** (`--live` only) call real search engines to measure availability
  and check the fallback chain earns its place. Off by default — CI must never
  fail because a provider is rate-limiting.

```bash
make test                 # contract tier only
pytest tests/eval --live  # add the live tier
```

The numbers the model card records come from `ai/notebooks/retrieval_eval.ipynb`.
This file asserts the properties; the notebook measures them.
"""

import time

import pytest

import t2url

ENGINES = ["duckduckgo", "yahoo", "startpage", "yandex"]

# A search that takes longer than this is unusable behind a synchronous form
# post, whatever it returns.
LATENCY_BUDGET_S = 20.0


def assert_retrieval_contract(urls, max_results):
    """Every guarantee `text_to_urls` makes, in one place.

    Both tiers call this, so a live run checks the same invariants as CI — the
    live tier differs only in whether a real engine produced the input.
    """
    assert isinstance(urls, list), "must return a list, never None"
    assert all(isinstance(u, str) for u in urls), "every element is a string"
    assert all(u for u in urls), "no empty strings"
    assert len(urls) == len(set(urls)), "deduplicated"
    assert len(urls) <= max_results, f"at most max_results ({max_results})"
    assert all(u.startswith(("http://", "https://")) for u in urls), \
        "absolute http(s) URLs only"


# --- Contract tier (always runs) -------------------------------------------

class TestRetrievalContract:
    @pytest.fixture
    def stub(self, monkeypatch):
        def _install(results):
            class Fake:
                def text(self, query, **kwargs):
                    return results
            monkeypatch.setattr(t2url, "DDGS", Fake)
        return _install

    def test_wellformed_response_satisfies_the_contract(self, stub, fake_results):
        stub(fake_results)
        assert_retrieval_contract(t2url.text_to_urls("cdp", max_results=10), 10)

    def test_duplicate_heavy_response_still_satisfies_it(self, stub):
        stub([{"href": "https://example.com/same"}] * 20)
        urls = t2url.text_to_urls("cdp", max_results=10)

        assert_retrieval_contract(urls, 10)
        assert len(urls) == 1

    def test_empty_response_satisfies_it(self, stub):
        stub([])
        assert_retrieval_contract(t2url.text_to_urls("cdp", max_results=10), 10)

    def test_null_response_satisfies_it(self, stub):
        """ddgs can return None rather than an empty list."""
        stub(None)
        assert_retrieval_contract(t2url.text_to_urls("cdp", max_results=10), 10)

    def test_malformed_entries_are_filtered_out(self, stub):
        stub([
            {"href": "https://example.com/good"},
            {"title": "no href at all"},
            {"href": None},
            {"href": ""},
        ])
        assert_retrieval_contract(t2url.text_to_urls("cdp", max_results=10), 10)

    def test_every_ui_engine_is_accepted(self, stub):
        """The four engines the UI exposes must all be valid `backend` values.
        A typo here means a UI toggle that silently returns nothing."""
        stub([{"href": "https://example.com/1"}])
        for engine in ENGINES:
            assert t2url.text_to_urls("cdp", backend=engine) == ["https://example.com/1"]

    def test_full_chain_is_accepted(self, stub):
        stub([{"href": "https://example.com/1"}])
        assert t2url.text_to_urls("cdp", backend=",".join(ENGINES))


# --- Live tier (--live only) -----------------------------------------------

@pytest.mark.live
class TestLiveRetrieval:
    """Calls real engines. Each test pauses afterwards to stay a good citizen."""

    COOLDOWN_S = 2

    @pytest.fixture(autouse=True)
    def cooldown(self):
        yield
        time.sleep(self.COOLDOWN_S)

    def test_default_engine_returns_results(self):
        """The one live check worth gating a release on: the default engine, on
        an easy query, returns something. If this fails the accelerator is down
        for every user regardless of what else passes."""
        urls = t2url.text_to_urls("cloudera cdp documentation", max_results=10)

        assert_retrieval_contract(urls, 10)
        assert urls, "default engine (duckduckgo) returned nothing"

    def test_within_the_latency_budget(self):
        start = time.monotonic()
        t2url.text_to_urls("iceberg table format", max_results=10)
        elapsed = time.monotonic() - start

        assert elapsed < LATENCY_BUDGET_S, \
            f"retrieval took {elapsed:.1f}s, budget is {LATENCY_BUDGET_S}s"

    def test_max_results_is_respected_by_real_engines(self):
        urls = t2url.text_to_urls("apache iceberg", max_results=5)
        assert_retrieval_contract(urls, 5)

    def test_fallback_chain_is_at_least_as_good_as_one_engine(self):
        """The chain exists so a throttled engine cannot fail a search. If it
        ever returns *fewer* results than the default alone, the ordering is
        wrong — see the overlap analysis in ai/notebooks/retrieval_eval.ipynb."""
        query = "cloudera data engineering spark"
        solo = t2url.text_to_urls(query, max_results=10)
        time.sleep(self.COOLDOWN_S)
        chained = t2url.text_to_urls(query, max_results=10, backend=",".join(ENGINES))

        assert_retrieval_contract(chained, 10)
        assert len(chained) >= len(solo)

    @pytest.mark.parametrize("engine", ENGINES)
    def test_engine_availability(self, engine):
        """Per-engine availability. Expected to be flaky by design — a failure
        here is a measurement, not necessarily a defect. Record it in the model
        card rather than muting the test."""
        urls = t2url.text_to_urls("apache iceberg", max_results=10, backend=engine)

        assert_retrieval_contract(urls, 10)
        if not urls:
            pytest.skip(f"{engine} returned nothing — throttled or blocked")
