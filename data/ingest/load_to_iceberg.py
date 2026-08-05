"""Ingest — load the SQLite dev store into the raw Iceberg tables.

The bridge between T2URL's two storage tiers. Reads `data/t2url.db` (whatever
`app/server.py` has been writing) and appends it to `t2url.raw_searches` and
`t2url.raw_search_urls`, created by `data/iceberg/ddl.sql`.

Dry-run needs nothing but the standard library, so it works on a laptop with no
CDP environment:

    python data/ingest/load_to_iceberg.py                 # plan only, no writes
    python data/ingest/load_to_iceberg.py --execute       # needs Spark + Iceberg

Only links are ingested, never page content — see governance/DATA_CLASSIFICATION.md.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent
DEFAULT_DB = DATA_DIR / "t2url.db"

# Column order here must match the Iceberg DDL. Kept explicit rather than
# SELECT * so a schema change fails loudly instead of silently misaligning.
SEARCH_COLUMNS = [
    "search_id", "query", "created_at", "region",
    "safesearch", "timelimit", "backend", "max_results",
]
URL_COLUMNS = ["search_id", "position", "url", "created_at"]

SEARCH_QUERY = """
    SELECT id AS search_id, query, created_at, region,
           safesearch, timelimit, backend, max_results
      FROM searches
     WHERE created_at > ?
     ORDER BY id
"""

URL_QUERY = """
    SELECT u.search_id, u.position, u.url, s.created_at
      FROM search_urls u
      JOIN searches s ON s.id = u.search_id
     WHERE s.created_at > ?
     ORDER BY u.search_id, u.position
"""


def read_sqlite(db_path, since):
    """Pull searches and their URLs out of the dev store as lists of dicts."""
    if not db_path.exists():
        raise SystemExit(
            f"No SQLite store at {db_path}.\n"
            "Run the app first (make dev) so there is something to ingest."
        )
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        searches = [dict(r) for r in conn.execute(SEARCH_QUERY, (since,))]
        urls = [dict(r) for r in conn.execute(URL_QUERY, (since,))]
    finally:
        conn.close()
    return searches, urls


def print_plan(searches, urls, args):
    """Show exactly what --execute would write, without writing it."""
    ingested_at = datetime.now(timezone.utc).isoformat()
    target = f"{args.catalog}.{args.database}" if args.catalog else args.database

    # Printed output stays ASCII: this runs on a Windows console where the
    # default cp1252 codec raises on characters like U+2192.
    print(f"T2URL ingest -- DRY RUN (no writes)\n{'=' * 52}")
    print(f"source     {args.db}")
    print(f"target     {target}")
    print(f"watermark  {args.since or '(none - full load)'}")
    print(f"ingested_at{'':<1} {ingested_at}\n")

    print(f"{'table':<28} {'rows':>8}")
    print("-" * 38)
    print(f"{target + '.raw_searches':<28} {len(searches):>8}")
    print(f"{target + '.raw_search_urls':<28} {len(urls):>8}")

    if not searches:
        print("\nNothing to load.")
        return

    span = (searches[0]["created_at"], searches[-1]["created_at"])
    print(f"\ncreated_at spans {span[0]} -> {span[1]}")
    print(f"distinct URLs in batch: {len({u['url'] for u in urls})} of {len(urls)}")
    print("\nsample rows (raw_searches):")
    for row in searches[:3]:
        print(f"  [{row['search_id']}] {row['query'][:56]!r} "
              f"backend={row['backend']} region={row['region']}")
    print("\nRe-run with --execute to write. Requires Spark with the Iceberg "
          "runtime and the tables from data/iceberg/ddl.sql.")


def load_to_iceberg(searches, urls, args):
    """Append both batches to Iceberg. Requires pyspark on the submit host."""
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except ImportError:
        raise SystemExit(
            "--execute needs pyspark. Run this as a Cloudera Data Engineering job, "
            "or from a Cloudera AI session where Spark is already on the path.\n"
            "Drop --execute to see the load plan instead."
        )

    if not searches:
        print("Nothing to load - no searches past the watermark.")
        return

    spark = (
        SparkSession.builder
        .appName("t2url-ingest")
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .getOrCreate()
    )
    prefix = f"{args.catalog}.{args.database}" if args.catalog else args.database

    def write(rows, columns, table):
        df = spark.createDataFrame([[r[c] for c in columns] for r in rows], columns)
        # created_at arrives as an ISO-8601 UTC string; Iceberg wants a real timestamp.
        df = (df.withColumn("created_at", F.to_timestamp("created_at"))
                .withColumn("ingested_at", F.current_timestamp()))
        df.writeTo(f"{prefix}.{table}").append()
        print(f"  appended {len(rows):>6} rows -> {prefix}.{table}")

    print(f"T2URL ingest -> {prefix}")
    write(searches, SEARCH_COLUMNS, "raw_searches")
    write(urls, URL_COLUMNS, "raw_search_urls")
    print("Done. Run pipelines/jobs/url_enrichment.py to refresh curated_urls.")
    spark.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help=f"SQLite dev store (default: {DEFAULT_DB})")
    parser.add_argument("--catalog", default="spark_catalog",
                        help="Iceberg catalog name (default: spark_catalog)")
    parser.add_argument("--database", default="t2url",
                        help="Target database (default: t2url)")
    parser.add_argument("--since", default="",
                        help="Only load searches with created_at greater than this "
                             "ISO-8601 UTC timestamp. Omit for a full load.")
    parser.add_argument("--execute", action="store_true",
                        help="Actually write. Without it, print the plan and exit.")
    args = parser.parse_args(argv)

    searches, urls = read_sqlite(args.db, args.since)
    if args.execute:
        load_to_iceberg(searches, urls, args)
    else:
        print_plan(searches, urls, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
