"""SQLite-backed session store, keyed by WhatsApp number."""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.state.models import SessionState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    wa_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    intent TEXT,
    locality TEXT,
    budget_min INTEGER,
    budget_max INTEGER,
    bhk INTEGER,
    timeline TEXT,
    selected_property_id INTEGER,
    stage TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_UPSERT = """
INSERT INTO sessions (
    wa_id, session_id, intent, locality, budget_min, budget_max,
    bhk, timeline, selected_property_id, stage, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(wa_id) DO UPDATE SET
    intent = excluded.intent,
    locality = excluded.locality,
    budget_min = excluded.budget_min,
    budget_max = excluded.budget_max,
    bhk = excluded.bhk,
    timeline = excluded.timeline,
    selected_property_id = excluded.selected_property_id,
    stage = excluded.stage,
    updated_at = excluded.updated_at
"""


class SessionStore:
    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get(self, wa_id: str) -> SessionState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE wa_id = ?", (wa_id,)
            ).fetchone()
        if row is None:
            return None
        return SessionState(
            session_id=row["session_id"],
            wa_id=row["wa_id"],
            intent=row["intent"],
            locality=row["locality"],
            budget_min=row["budget_min"],
            budget_max=row["budget_max"],
            bhk=row["bhk"],
            timeline=row["timeline"],
            selected_property_id=row["selected_property_id"],
            stage=row["stage"],
        )

    def get_or_create(self, wa_id: str) -> SessionState:
        existing = self.get(wa_id)
        if existing is not None:
            return existing
        state = SessionState(session_id=uuid4().hex, wa_id=wa_id)
        self.save(state)
        return state

    def save(self, state: SessionState) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                _UPSERT,
                (
                    state.wa_id,
                    state.session_id,
                    state.intent,
                    state.locality,
                    state.budget_min,
                    state.budget_max,
                    state.bhk,
                    state.timeline,
                    state.selected_property_id,
                    state.stage,
                    now,
                    now,
                ),
            )
