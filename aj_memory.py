import json
import os
import time
from datetime import datetime

MEMORY_FILE = "aj_memory.json"

# ============================================================
# AJ 3.0 — LONG-TERM INTELLIGENT MEMORY
# ============================================================

MEMORY_VERSION = 2
MAX_MEMORIES_PER_CATEGORY = 100
MAX_VALUE_LENGTH = 2000

DEFAULT_MEMORY = {
    "version": MEMORY_VERSION,
    "profile": {},
    "preferences": {},
    "projects": {},
    "important": {},
    "facts": {},
    "conversation": {}
}


def _empty_memory():
    return {
        "version": MEMORY_VERSION,
        "profile": {},
        "preferences": {},
        "projects": {},
        "important": {},
        "facts": {},
        "conversation": {}
    }


def _normalize_value(value):
    """Keep stored memory compact and JSON-safe."""
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return value.strip()[:MAX_VALUE_LENGTH]
        return value

    return str(value)[:MAX_VALUE_LENGTH]


def _normalize_memory(memory):
    """Upgrade old AJ memory format without losing existing data."""
    if not isinstance(memory, dict):
        return _empty_memory()

    # Old AJ memory was a simple key/value dictionary.
    # Preserve those values inside the facts category.
    if "version" not in memory:
        upgraded = _empty_memory()

        for key, value in memory.items():
            if key in {"user_name", "assistant_name", "creator", "project"}:
                upgraded["profile"][key] = _normalize_value(value)
            else:
                upgraded["facts"][key] = _normalize_value(value)

        return upgraded

    normalized = _empty_memory()

    for category in normalized:
        if category == "version":
            continue

        value = memory.get(category, {})
        if isinstance(value, dict):
            normalized[category] = value
        else:
            normalized[category] = {}

    normalized["version"] = MEMORY_VERSION
    return normalized


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return _empty_memory()

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            memory = json.load(file)

        return _normalize_memory(memory)

    except Exception:
        return _empty_memory()


def save_memory(memory):
    memory = _normalize_memory(memory)

    # Atomic write reduces the chance of leaving a broken JSON file.
    temporary_file = MEMORY_FILE + ".tmp"

    with open(
        temporary_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            memory,
            file,
            indent=4,
            ensure_ascii=False
        )

    os.replace(temporary_file, MEMORY_FILE)


def remember(key, value):
    """
    Backward-compatible memory function.

    Existing AJ code can continue using:
        remember("key", "value")

    Simple keys are stored as facts, while known profile
    fields remain in the profile category.
    """
    memory = load_memory()

    if key in {
        "user_name",
        "assistant_name",
        "creator",
        "project"
    }:
        category = "profile"
    else:
        category = "facts"

    memory[category][str(key)] = _normalize_value(value)
    save_memory(memory)


def remember_in(category, key, value):
    """Store a memory in a specific category."""
    memory = load_memory()

    valid_categories = {
        "profile",
        "preferences",
        "projects",
        "important",
        "facts",
        "conversation"
    }

    if category not in valid_categories:
        category = "facts"

    category_data = memory.setdefault(category, {})

    # Limit category size by removing the oldest entries.
    if key not in category_data and len(category_data) >= MAX_MEMORIES_PER_CATEGORY:
        oldest_key = next(iter(category_data))
        del category_data[oldest_key]

    category_data[str(key)] = {
        "value": _normalize_value(value),
        "updated_at": datetime.now().isoformat(timespec="seconds")
    }

    save_memory(memory)


def _unwrap(value):
    """Return the actual value from a structured memory entry."""
    if isinstance(value, dict) and "value" in value:
        return value["value"]

    return value


def recall(key):
    """Backward-compatible lookup across all memory categories."""
    memory = load_memory()

    for category in [
        "profile",
        "preferences",
        "projects",
        "important",
        "facts",
        "conversation"
    ]:
        if key in memory.get(category, {}):
            return _unwrap(memory[category][key])

    return None


def recall_from(category, key):
    """Recall a value from one specific category."""
    memory = load_memory()
    value = memory.get(category, {}).get(key)

    if value is None:
        return None

    return _unwrap(value)


def search_memory(query, limit=10):
    """
    Search stored memories by key/value text.

    This is intentionally local and lightweight. It does not send
    memory contents to any external service.
    """
    query = str(query).strip().lower()

    if not query:
        return []

    memory = load_memory()
    results = []

    categories = [
        "profile",
        "preferences",
        "projects",
        "important",
        "facts",
        "conversation"
    ]

    for category in categories:
        for key, raw_value in memory.get(category, {}).items():
            value = _unwrap(raw_value)

            searchable = f"{key} {value}".lower()

            if query in searchable:
                results.append({
                    "category": category,
                    "key": key,
                    "value": value
                })

    return results[:max(1, int(limit))]


def get_relevant_memory(query, limit=8):
    """
    Return simple relevance-ranked memories.

    Exact key matches receive priority, followed by matches in
    stored values.
    """
    query = str(query).strip().lower()

    if not query:
        return []

    memory = load_memory()
    scored = []

    categories = [
        "profile",
        "preferences",
        "projects",
        "important",
        "facts",
        "conversation"
    ]

    query_words = {
        word for word in query.split()
        if len(word) > 2
    }

    for category in categories:
        for key, raw_value in memory.get(category, {}).items():
            value = _unwrap(raw_value)

            key_text = str(key).lower()
            value_text = str(value).lower()
            combined = f"{key_text} {value_text}"

            score = 0

            if query in key_text:
                score += 5

            if query in value_text:
                score += 4

            for word in query_words:
                if word in combined:
                    score += 1

            if score > 0:
                scored.append({
                    "score": score,
                    "category": category,
                    "key": key,
                    "value": value
                })

    scored.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return [
        {
            "category": item["category"],
            "key": item["key"],
            "value": item["value"]
        }
        for item in scored[:max(1, int(limit))]
    ]


def get_all_memory():
    return load_memory()


def get_memory_summary():
    """Return a compact summary useful to AJ's reasoning layer."""
    memory = load_memory()

    summary = {}

    for category in [
        "profile",
        "preferences",
        "projects",
        "important",
        "facts",
        "conversation"
    ]:
        items = memory.get(category, {})

        summary[category] = {
            key: _unwrap(value)
            for key, value in items.items()
        }

    return summary


def forget(key, category=None):
    """Forget one stored memory."""
    memory = load_memory()

    if category:
        categories = [category]
    else:
        categories = [
            "profile",
            "preferences",
            "projects",
            "important",
            "facts",
            "conversation"
        ]

    removed = False

    for current_category in categories:
        category_data = memory.get(current_category, {})

        if key in category_data:
            del category_data[key]
            removed = True

    if removed:
        save_memory(memory)

    return removed


def clear_memory():
    """Clear all AJ long-term memory."""
    save_memory(_empty_memory())


def memory_count():
    """Return the number of stored memory entries."""
    memory = load_memory()

    total = 0

    for category in [
        "profile",
        "preferences",
        "projects",
        "important",
        "facts",
        "conversation"
    ]:
        total += len(memory.get(category, {}))

    return total


def export_memory():
    """Return a JSON-safe copy of all stored memory."""
    return load_memory()
