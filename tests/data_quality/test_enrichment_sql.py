"""Schema alignment between the enrichment job and the Iceberg DDL.

`url_enrichment.MERGE_SQL` ends in `WHEN NOT MATCHED THEN INSERT *`, which binds
the staged columns to `curated_urls` **positionally**. Reorder either side and
Spark inserts happily with the values in the wrong columns — no error, just
`providers` full of timestamps. Nothing else in the suite would notice, because
running the job needs a cluster.

These are string checks against the two files. That is a blunt instrument, but it
is the only guard available without Spark, and the failure it prevents is silent.
"""

import re
from pathlib import Path

import url_enrichment

ROOT = Path(__file__).resolve().parent.parent.parent
DDL = (ROOT / "data" / "iceberg" / "ddl.sql").read_text(encoding="utf-8")


def ddl_columns(table):
    """Column names of `table`, in declaration order, from the Iceberg DDL."""
    body = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\)", DDL, re.S).group(1)
    names = []
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("--"):
            names.append(line.split()[0])
    return names


def staged_aliases():
    """Output column names of STAGE_SQL, in select order."""
    select = url_enrichment.STAGE_SQL.split("FROM")[0]
    names = []
    for part in select.replace("SELECT", "").split(","):
        part = part.strip()
        if not part:
            continue
        names.append(part.split(" AS ")[-1].strip() if " AS " in part else part)
    return names


class TestCuratedUrlsAlignment:
    def test_staged_columns_match_curated_urls_exactly(self):
        """Same names, same order — this is what `INSERT *` relies on."""
        assert staged_aliases() == ddl_columns("t2url.curated_urls")

    def test_providers_is_carried_all_the_way_through(self):
        assert "providers" in staged_aliases()
        assert "providers" in ddl_columns("t2url.curated_urls")

    def test_every_aggregate_is_also_merged_on_conflict(self):
        """An aggregate in the INSERT but not the UPDATE freezes at its first
        value: a new sighting would land for an unseen URL and be silently
        dropped for a known one. `providers` is exactly this shape, so it is the
        column most likely to be added in one clause and forgotten in the other.

        Group-by keys are exempt — they are functionally determined by `url`, so
        they cannot change for a row the MERGE matched.
        """
        # Scoped to the SET block: the ON clause also mentions `target.url`, and
        # matching on a key is not the same as updating it.
        set_block = url_enrichment.MERGE_SQL.split("UPDATE SET")[1].split("WHEN")[0]
        merged = set(re.findall(r"target\.(\w+)\s*=", set_block))
        group_by = {c.strip() for c in
                    url_enrichment.STAGE_SQL.split("GROUP BY")[1].split(",")}

        assert set(staged_aliases()) - merged == group_by
        assert "providers" in merged


class TestRawTableAlignment:
    def test_enrichment_reads_columns_the_raw_table_declares(self):
        """The job selects `provider` off raw_search_urls; the DDL must have it."""
        raw = ddl_columns("t2url.raw_search_urls")

        assert "provider" in raw
        assert "url" in raw and "position" in raw and "search_id" in raw
