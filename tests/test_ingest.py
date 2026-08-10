"""Ingest layer — the SQLite -> Iceberg bridge in `data/ingest/load_to_iceberg.py`.

Only `read_sqlite` and the column lists are exercised; the Spark write needs a
cluster and is out of scope here (see tests/README.md, "What is not covered").

That still catches the failure this module is most prone to. Its SELECTs name
columns explicitly so a schema change fails loudly rather than misaligning — but
"loudly" means *at ingest time*, which on a real deployment is a scheduled 02:00
job, long after the change that broke it. These tests move that failure forward.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# data/ingest/ is not a package and not on sys.path, so load it by file path
# rather than adding a fourth layer directory to conftest for one module.
_spec = importlib.util.spec_from_file_location(
    "load_to_iceberg", ROOT / "data" / "ingest" / "load_to_iceberg.py")
ingest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ingest)


@pytest.fixture
def populated_db(temp_db):
    """Two searches from different corpora, so provenance has something to lose."""
    temp_db.save_search(
        "iceberg", ["https://ko.wikipedia.org/wiki/X"],
        provider="wikipedia", region="kr-kr",
        safesearch=None, timelimit=None, backend=None, max_results=10,
    )
    temp_db.save_search(
        "iceberg", ["https://iceberg.apache.org/", "https://example.com/1"],
        provider="ddgs", region="wt-wt",
        safesearch="moderate", timelimit="", backend="duckduckgo,yahoo",
        max_results=10,
    )
    return temp_db


class TestReadSqlite:
    def test_reads_both_tables(self, populated_db):
        searches, urls = ingest.read_sqlite(populated_db.DB_PATH, "")

        assert len(searches) == 2
        assert len(urls) == 3

    def test_searches_carry_the_provider(self, populated_db):
        searches, _ = ingest.read_sqlite(populated_db.DB_PATH, "")

        assert [s["provider"] for s in searches] == ["wikipedia", "ddgs"]

    def test_urls_carry_their_own_provider(self, populated_db):
        """Read off `search_urls`, not the join — a URL keeps its provenance even
        after deduplication collapses it away from its original search."""
        _, urls = ingest.read_sqlite(populated_db.DB_PATH, "")
        by_url = {u["url"]: u["provider"] for u in urls}

        assert by_url["https://ko.wikipedia.org/wiki/X"] == "wikipedia"
        assert by_url["https://iceberg.apache.org/"] == "ddgs"

    def test_unsupported_options_stay_null_through_ingest(self, populated_db):
        """The NULL/"" distinction has to survive into the lakehouse or the
        governed table inherits the same false claim the dev store avoided."""
        searches, _ = ingest.read_sqlite(populated_db.DB_PATH, "")
        wiki, web = searches[0], searches[1]

        assert wiki["timelimit"] is None    # wikipedia has no time filter
        assert web["timelimit"] == ""       # ddgs has one, unused
        assert wiki["backend"] is None

    def test_watermark_filters_by_created_at(self, populated_db):
        searches, urls = ingest.read_sqlite(populated_db.DB_PATH, "2999-01-01T00:00:00+00:00")

        assert searches == [] and urls == []

    def test_missing_database_fails_with_a_usable_message(self, tmp_path):
        with pytest.raises(SystemExit, match="make dev"):
            ingest.read_sqlite(tmp_path / "absent.db", "")


class TestColumnAlignment:
    """`load_to_iceberg` builds DataFrames positionally from these lists, so a
    name that drifts from the SELECT misaligns columns instead of erroring."""

    def test_search_columns_match_the_query(self, populated_db):
        searches, _ = ingest.read_sqlite(populated_db.DB_PATH, "")

        assert list(searches[0]) == ingest.SEARCH_COLUMNS

    def test_url_columns_match_the_query(self, populated_db):
        _, urls = ingest.read_sqlite(populated_db.DB_PATH, "")

        assert list(urls[0]) == ingest.URL_COLUMNS

    def test_every_sqlite_search_column_reaches_the_lakehouse(self, populated_db):
        """A column added to schema.sql but not to the ingest SELECT is invisible
        downstream — the dev store would have it and Iceberg silently would not."""
        with sqlite3.connect(populated_db.DB_PATH) as conn:
            local = {r[1] for r in conn.execute("PRAGMA table_info(searches)")}

        # `id` is renamed to search_id on the way out.
        assert local - {"id"} <= set(ingest.SEARCH_COLUMNS)

    def test_every_sqlite_url_column_reaches_the_lakehouse(self, populated_db):
        with sqlite3.connect(populated_db.DB_PATH) as conn:
            local = {r[1] for r in conn.execute("PRAGMA table_info(search_urls)")}

        # `id` is a local surrogate key; created_at is denormalised from the parent.
        assert local - {"id"} <= set(ingest.URL_COLUMNS)
