"""Loads property fixtures from local JSON (locked stack: no external DB)."""

import json
from pathlib import Path

from app.properties.models import Property

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "properties.json"


class PropertyRepository:
    def __init__(self, data_path: str | Path = DEFAULT_DATA_PATH):
        raw = json.loads(Path(data_path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Property data must be a JSON array")
        self._properties = tuple(Property(**record) for record in raw)
        self._by_id = {prop.id: prop for prop in self._properties}

    def all(self) -> tuple[Property, ...]:
        return self._properties

    def get(self, property_id: int) -> Property | None:
        return self._by_id.get(property_id)
