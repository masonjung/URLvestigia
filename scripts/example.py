"""Quick demo of the t2url library."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "retrieval"))

from t2url import text_to_urls

if __name__ == "__main__":
    for url in text_to_urls("Cloudera CDP supports use cases", max_results=16):
        print(url)
