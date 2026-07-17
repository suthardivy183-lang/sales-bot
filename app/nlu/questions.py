"""Map a customer question to the property record fields it asks about.

Amenity keywords deliberately map to field names that do NOT exist on the
fixtures (private_pool, gym, ...) — the Verification Agent is what turns that
absence into an honest refusal instead of a confident hallucination.
"""

_RECORD_FIELD_KEYWORDS = {
    "price": ("price", "cost", "how much", "kitna", "kimat"),
    "possession": ("possession", "handover", "when will it be ready", "when is it ready"),
    "status": ("ready", "under construction", "status"),
}

_AMENITY_FIELD_KEYWORDS = {
    "private_pool": ("pool", "swimming"),
    "gym": ("gym", "fitness centre", "fitness center"),
    "garden": ("garden", "lawn"),
    "parking": ("parking", "car park"),
    "clubhouse": ("clubhouse", "club house"),
}


def fields_asked_about(text: str) -> list[str]:
    """Evidence fields the message asks about, in detection order."""
    normalized = " ".join(text.lower().split())
    fields = [
        field
        for keyword_map in (_AMENITY_FIELD_KEYWORDS, _RECORD_FIELD_KEYWORDS)
        for field, keywords in keyword_map.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    # A possession question is also answerable via the status field
    # (e.g. ready-to-move flats have no possession date at all).
    if "possession" in fields and "status" not in fields:
        fields.append("status")
    return fields
