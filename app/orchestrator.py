"""Orchestrator Agent — plans and routes each turn using current state.

Routing per turn (first match wins):
1. booking request  (needs a target property)   -> idempotent booking + CRM
2. EMI request      (needs a target property)   -> deterministic EMI tool
3. property question (only once matched)        -> field answer via verifier
4. everything else                              -> qualification turn

The Verification Agent gates EVERY reply that carries property facts —
nothing reaches the customer unverified (engineering rule 3).
"""

import logging

from app.actions.booking import BookingTool
from app.actions.crm import CrmTool
from app.actions.models import SlotUnavailableError
from app.agents.claims import Claim, DraftReply
from app.agents.qualification import QualificationAgent, next_question
from app.agents.response import ResponseGenerator
from app.agents.verification import VerificationAgent
from app.gateway.schemas import IncomingMessage
from app.nlu.intents import wants_booking, wants_emi
from app.nlu.questions import fields_asked_about
from app.nlu.rules import extract_locality
from app.privacy import mask_phone
from app.properties.models import Property
from app.properties.repository import PropertyRepository
from app.state.models import SessionState, Stage
from app.state.store import SessionStore
from app.tools.emi import quote_for_property_price
from app.tools.property_search import criteria_from_state, search

logger = logging.getLogger(__name__)

BOOKING_HINT = "Want to see it in person? Just say 'book a viewing'."
NO_MATCH_REPLY = (
    "I don't have a verified listing that matches all of that right now. "
    "Want to adjust the budget or try a nearby locality?"
)
GENERIC_PROMPT = (
    "Happy to help further — ask about the EMI, property details, "
    "or say 'book a viewing'."
)
NO_SLOTS_REPLY = (
    "All viewing slots are currently taken — a human agent will call you "
    "to arrange a time."
)

_PROFILE_FIELDS = ("intent", "locality", "budget_min", "budget_max", "bhk", "timeline")


class Orchestrator:
    def __init__(
        self,
        store: SessionStore,
        agent: QualificationAgent,
        repository: PropertyRepository,
        generator: ResponseGenerator,
        verifier: VerificationAgent,
        crm: CrmTool,
        booking: BookingTool,
    ):
        self._store = store
        self._agent = agent
        self._repository = repository
        self._generator = generator
        self._verifier = verifier
        self._crm = crm
        self._booking = booking

    def handle_message(self, message: IncomingMessage) -> str:
        state = self._store.get_or_create(message.wa_id)
        target = self._target_property(state, message.text)
        logger.info(
            "Turn from %s (stage=%s)", mask_phone(message.wa_id), state.stage
        )

        if wants_booking(message.text) and target is not None:
            return self._handle_booking(state, message, target)
        if wants_emi(message.text) and target is not None:
            return self._handle_emi(target)
        fields = fields_asked_about(message.text)
        if fields and target is not None and state.stage in (Stage.MATCHED, Stage.BOOKED):
            return self._handle_field_question(state, message, target, fields)
        return self._handle_qualification(state, message)

    def _target_property(
        self, state: SessionState, text: str
    ) -> Property | None:
        """The property this turn is about: an explicitly mentioned locality
        wins over the selected property only when it names a different area."""
        selected = (
            self._repository.get(state.selected_property_id)
            if state.selected_property_id is not None
            else None
        )
        mentioned = extract_locality(text)
        if mentioned is None:
            return selected
        if selected is not None and selected.locality == mentioned:
            return selected
        for prop in self._repository.all():
            if prop.locality == mentioned:
                return prop
        return selected

    def _handle_booking(
        self, state: SessionState, message: IncomingMessage, target: Property
    ) -> str:
        try:
            booking = self._booking.book(message.message_id, message.wa_id)
        except SlotUnavailableError:
            self._crm.write_lead(
                message.message_id,
                state,
                note="booking failed: no slots left",
                property_id=target.id,
            )
            return NO_SLOTS_REPLY

        draft = DraftReply(
            text=(
                f"Done! Your viewing of the {target.bhk}BHK in "
                f"{target.locality} (property #{target.id}) is booked for "
                f"{booking.slot_label}. Our agent will meet you there."
            ),
            claims=(
                Claim(
                    statement=f"{target.bhk}BHK",
                    property_id=target.id,
                    evidence_field="bhk",
                    claimed_value=target.bhk,
                ),
                Claim(
                    statement=f"located in {target.locality}",
                    property_id=target.id,
                    evidence_field="locality",
                    claimed_value=target.locality,
                ),
            ),
        )
        verified = self._verifier.verify(draft)
        booked_state = state.model_copy(update={"stage": Stage.BOOKED})
        self._store.save(booked_state)
        self._crm.write_lead(
            message.message_id,
            booked_state,
            note=f"viewing booked: {booking.slot_label}",
            property_id=target.id,
        )
        return verified.text

    def _handle_emi(self, target: Property) -> str:
        quote = quote_for_property_price(target.price)
        verified = self._verifier.verify(self._generator.emi_reply(target, quote))
        return verified.text

    def _handle_field_question(
        self,
        state: SessionState,
        message: IncomingMessage,
        target: Property,
        fields: list[str],
    ) -> str:
        draft = self._generator.field_answer_reply(target, fields)
        verified = self._verifier.verify(draft)
        if verified.escalate:
            self._crm.write_lead(
                message.message_id,
                state,
                note=f"HANDOFF: could not verify question about {', '.join(fields)}",
                property_id=target.id,
            )
        return verified.text

    def _handle_qualification(
        self, state: SessionState, message: IncomingMessage
    ) -> str:
        new_state = self._agent.process_turn(state, message.text)
        profile_changed = any(
            getattr(new_state, field) != getattr(state, field)
            for field in _PROFILE_FIELDS
        )
        should_search = new_state.stage == Stage.QUALIFIED or (
            new_state.stage == Stage.MATCHED and profile_changed
        )
        if should_search:
            return self._present_matches(new_state, message)

        self._store.save(new_state)
        question = next_question(new_state)
        return question if question is not None else GENERIC_PROMPT

    def _present_matches(
        self, state: SessionState, message: IncomingMessage
    ) -> str:
        results = search(
            self._repository.all(), criteria_from_state(state), message.text
        )
        if not results:
            self._store.save(state)
            self._crm.write_lead(
                message.message_id, state, note="qualified; no verified match"
            )
            return NO_MATCH_REPLY

        verified = self._verifier.verify(self._generator.properties_reply(results))
        matched_state = state.model_copy(
            update={"stage": Stage.MATCHED, "selected_property_id": results[0].id}
        )
        self._store.save(matched_state)
        self._crm.write_lead(
            message.message_id,
            matched_state,
            note=f"qualified; presented properties {[p.id for p in results]}",
            property_id=results[0].id,
        )
        return f"{verified.text}\n\n{BOOKING_HINT}"
