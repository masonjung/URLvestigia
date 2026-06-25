"""Optional LLM augmentation — expand natural-language input into focused
search queries using Claude before hitting DuckDuckGo.

This module is only imported when ``augment=True`` is requested, so the
``anthropic`` dependency stays optional for plain search.
"""

from __future__ import annotations

import json

_MODEL = "claude-opus-4-8"

_SYSTEM = (
    "You turn a user's natural-language request into a small set of focused "
    "web search queries that will surface the most relevant pages. Produce "
    "between 1 and {n} short keyword-style queries (not full sentences). "
    "Cover distinct angles of the request; do not repeat near-identical queries."
)

# Structured-output schema: a JSON object with a "queries" string array.
_FORMAT = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "queries": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["queries"],
        "additionalProperties": False,
    },
}


def expand_queries(
    text: str,
    *,
    max_queries: int = 3,
    model: str = _MODEL,
    client=None,
) -> list[str]:
    """Use Claude to rewrite/expand ``text`` into focused search queries.

    Args:
        text: The user's natural-language input.
        max_queries: Upper bound on the number of queries to generate.
        model: Anthropic model ID.
        client: An ``anthropic.Anthropic`` instance. If ``None``, one is
            constructed from the environment (``ANTHROPIC_API_KEY``).

    Returns:
        A list of search-query strings. Falls back to ``[text]`` if the model
        returns nothing usable (e.g. a refusal or empty output).

    Raises:
        RuntimeError: If the ``anthropic`` package is missing or the client
            cannot be constructed (e.g. no API key).
    """
    text = text.strip()
    if not text:
        return []

    if client is None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "augment=True requires the 'anthropic' package. "
                "Install it with: pip install anthropic"
            ) from exc
        try:
            client = anthropic.Anthropic()
        except Exception as exc:  # missing/invalid key, etc.
            raise RuntimeError(
                "Could not initialize the Anthropic client. "
                "Is ANTHROPIC_API_KEY set? "
                f"({exc})"
            ) from exc
        # The client constructs without credentials but fails at request time
        # with an opaque TypeError — surface a clear message upfront instead.
        if not (getattr(client, "api_key", None) or getattr(client, "auth_token", None)):
            raise RuntimeError(
                "No Anthropic credentials found. Set ANTHROPIC_API_KEY to use "
                "the 'Refine with AI' option."
            )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM.format(n=max_queries),
        messages=[{"role": "user", "content": text}],
        output_config={"format": _FORMAT},
    )

    queries = _parse_queries(response)
    cleaned = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
    return cleaned[:max_queries] or [text]


def _parse_queries(response) -> list[str]:
    """Pull the ``queries`` array out of a structured-output response.

    Returns an empty list on a refusal, empty content, or malformed JSON so the
    caller can fall back to the original text.
    """
    if getattr(response, "stop_reason", None) == "refusal":
        return []

    text_out = next(
        (b.text for b in response.content if getattr(b, "type", None) == "text"),
        None,
    )
    if not text_out:
        return []

    try:
        data = json.loads(text_out)
    except (json.JSONDecodeError, TypeError):
        return []

    queries = data.get("queries") if isinstance(data, dict) else None
    return queries if isinstance(queries, list) else []
