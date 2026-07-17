"""Idempotency ledger (engineering rule 6).

Every side-effecting action is keyed by (WhatsApp message ID, action name).
A replayed webhook event finds its stored result here and the action is never
re-executed — regardless of which backend performed it.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS action_log (
    message_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (message_id, action)
)
"""


class ActionLedger:
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

    def get(self, message_id: str, action: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM action_log WHERE message_id = ? AND action = ?",
                (message_id, action),
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def record(self, message_id: str, action: str, payload: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO action_log "
                "(message_id, action, payload, created_at) VALUES (?, ?, ?, ?)",
                (
                    message_id,
                    action,
                    json.dumps(payload),
                    datetime.now(UTC).isoformat(),
                ),
            )
