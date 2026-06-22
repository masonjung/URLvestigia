"""Quick demo of the t2url library."""

from t2url import text_to_urls

if __name__ == "__main__":
    query = "lightweight python libraries for parsing HTML"

    print("== Plain search ==")
    for url in text_to_urls(query, max_results=5):
        print(url)

    # Requires ANTHROPIC_API_KEY in the environment.
    # print("\n== LLM-augmented search ==")
    # for url in text_to_urls(query, max_results=5, augment=True):
    #     print(url)
