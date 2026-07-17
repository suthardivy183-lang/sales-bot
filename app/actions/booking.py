"""Viewing-slot booking — idempotent by WhatsApp message ID (rule 6).

Slots are a fixed demo fixture. The bookings table's PRIMARY KEY on slot_id
makes double-booking structurally impossible; the ActionLedger makes webhook
replays return the original booking instead of taking a second slot.
"""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.actions.ledger import ActionLedger
from app.actions.models import BookingResult, Slot, SlotUnavailableError
from app.privacy import mask_phone

BOOKING_ACTION = "booking"

DEFAULT_SLOTS = (
    Slot(slot_id="slot-1", label="Saturday 11:00"),
    Slot(slot_id="slot-2", label="Saturday 15:00"),
    Slot(slot_id="slot-3", label="Sunday 11:00"),
    Slot(slot_id="slot-4", label="Sunday 15:00"),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    slot_id TEXT PRIMARY KEY,
    wa_id_masked TEXT NOT NULL,
    message_id TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


class BookingTool:
    def __init__(
        self,
        db_path: str | Path,
        ledger: ActionLedger,
        slots: tuple[Slot, ...] = DEFAULT_SLOTS,
    ):
        self._db_path = str(db_path)
        self._ledger = ledger
        self._slots = {slot.slot_id: slot for slot in slots}
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

    def available_slots(self) -> list[Slot]:
        with self._connect() as conn:
            taken = {
                row["slot_id"]
                for row in conn.execute("SELECT slot_id FROM bookings")
            }
        return [
            slot for slot_id, slot in self._slots.items() if slot_id not in taken
        ]

    def book(
        self, message_id: str, wa_id: str, slot_id: str | None = None
    ) -> BookingResult:
        replayed = self._ledger.get(message_id, BOOKING_ACTION)
        if replayed is not None:
            return BookingResult(created=False, **replayed)

        candidates = (
            [slot_id]
            if slot_id is not None
            else [slot.slot_id for slot in self.available_slots()]
        )
        masked = mask_phone(wa_id)
        booked = self._try_book(candidates, masked, message_id)
        payload = {
            "slot_id": booked.slot_id,
            "slot_label": booked.label,
            "wa_id_masked": masked,
            "message_id": message_id,
        }
        self._ledger.record(message_id, BOOKING_ACTION, payload)
        return BookingResult(created=True, **payload)

    def _try_book(
        self, candidates: list[str], wa_id_masked: str, message_id: str
    ) -> Slot:
        now = datetime.now(UTC).isoformat()
        for candidate in candidates:
            slot = self._slots.get(candidate)
            if slot is None:
                continue
            try:
                with self._connect() as conn:
                    conn.execute(
                        "INSERT INTO bookings "
                        "(slot_id, wa_id_masked, message_id, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (slot.slot_id, wa_id_masked, message_id, now),
                    )
                return slot
            except sqlite3.IntegrityError:
                continue  # slot taken between listing and insert — try the next
        raise SlotUnavailableError("No viewing slots available")
