"""Heuristics for deciding when to enable web search tools."""


def should_enable_web_search(query: str, history: list[dict]) -> bool:
    """Decide whether to enable web search tools based on conversational context."""
    query_lower = query.lower()
    trigger_phrases = [
        "search the web",
        "web search",
        "browse",
        "look up",
        "find sources",
        "sources",
        "citations",
        "news",
        "latest",
        "recent",
        "today",
        "this week",
        "current",
        "price",
        "stock",
        "weather",
        "release date",
        "release notes",
        "breaking",
        "updates",
    ]
    if any(trigger in query_lower for trigger in trigger_phrases):
        return True

    for msg in reversed(history[-4:]):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").lower()
        if any(trigger in content for trigger in trigger_phrases):
            return True

    return False
