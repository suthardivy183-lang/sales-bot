"""Response Generator: drafts replies plus the structured claims behind them.

The generator drafts ASSERTIVELY — including for fields the record does not
have — deliberately playing the role of a confident LLM. It never gets to send
anything: the Verification Agent gates every draft. When an LLM-backed
generator replaces the templates here, the claims contract and the gate stay
exactly the same.
"""

from app.agents.claims import Claim, DraftReply
from app.inr import format_inr
from app.properties.models import Property
from app.tools.emi import EMIQuote

_OPTIMISTIC_LABELS = {
    "private_pool": "a private pool",
    "gym": "a gym",
    "garden": "a garden",
    "parking": "reserved parking",
    "clubhouse": "a clubhouse",
    "possession": "a confirmed possession date",
}


def _status_words(prop: Property) -> str:
    return prop.status.value.replace("_", " ")


def _fact_claims(prop: Property) -> list[Claim]:
    claims = [
        Claim(
            statement=f"{prop.bhk}BHK",
            property_id=prop.id,
            evidence_field="bhk",
            claimed_value=prop.bhk,
        ),
        Claim(
            statement=f"located in {prop.locality}",
            property_id=prop.id,
            evidence_field="locality",
            claimed_value=prop.locality,
        ),
        Claim(
            statement=f"priced at {format_inr(prop.price)}",
            property_id=prop.id,
            evidence_field="price",
            claimed_value=prop.price,
        ),
        Claim(
            statement=_status_words(prop),
            property_id=prop.id,
            evidence_field="status",
            claimed_value=prop.status.value,
        ),
    ]
    if prop.possession is not None:
        claims.append(
            Claim(
                statement=f"possession due {prop.possession}",
                property_id=prop.id,
                evidence_field="possession",
                claimed_value=prop.possession,
            )
        )
    return claims


class ResponseGenerator:
    def properties_reply(self, properties: list[Property]) -> DraftReply:
        lines = ["Here's what matches your requirements:"]
        claims: list[Claim] = []
        for position, prop in enumerate(properties, start=1):
            possession_note = (
                f", possession {prop.possession}" if prop.possession else ""
            )
            lines.append(
                f"{position}. {prop.bhk}BHK in {prop.locality} — "
                f"{format_inr(prop.price)}, {_status_words(prop)}"
                f"{possession_note} (property #{prop.id})"
            )
            claims.extend(_fact_claims(prop))
        return DraftReply(text="\n".join(lines), claims=tuple(claims))

    def emi_reply(self, prop: Property, quote: EMIQuote) -> DraftReply:
        down_percent = (1 - quote.principal / prop.price) * 100
        text = (
            f"For the {prop.bhk}BHK in {prop.locality} listed at "
            f"{format_inr(prop.price)}: assuming {down_percent:g}% down payment "
            f"and {quote.annual_rate_percent:g}% p.a. over "
            f"{quote.tenure_months // 12} years, the EMI works out to "
            f"₹{quote.monthly_emi:,}/month on a loan of {format_inr(quote.principal)}."
        )
        return DraftReply(
            text=text, claims=tuple(_fact_claims(prop)), emi_quote=quote
        )

    def field_answer_reply(self, prop: Property, fields: list[str]) -> DraftReply:
        sentences: list[str] = []
        claims: list[Claim] = []
        for field in fields:
            known = self._known_field_answer(prop, field)
            if known is not None:
                sentence, claim = known
            else:
                # Assertive draft for evidence the record does not have —
                # this is exactly what the Verification Agent must block.
                label = _OPTIMISTIC_LABELS.get(field, field.replace("_", " "))
                sentence = f"Yes — it has {label}."
                claim = Claim(
                    statement=label,
                    property_id=prop.id,
                    evidence_field=field,
                    claimed_value=True,
                )
            sentences.append(sentence)
            claims.append(claim)
        return DraftReply(text=" ".join(sentences), claims=tuple(claims))

    def _known_field_answer(
        self, prop: Property, field: str
    ) -> tuple[str, Claim] | None:
        if field not in Property.model_fields:
            return None
        value = getattr(prop, field)
        if value is None:
            return None
        sentences = {
            "price": f"It's priced at {format_inr(prop.price)}.",
            "bhk": f"It's a {prop.bhk}BHK.",
            "locality": f"It's located in {prop.locality}.",
            "status": f"It is {_status_words(prop)}.",
            "possession": f"Possession is due {prop.possession}.",
        }
        statements = {
            "price": f"priced at {format_inr(prop.price)}",
            "bhk": f"{prop.bhk}BHK",
            "locality": f"located in {prop.locality}",
            "status": _status_words(prop),
            "possession": f"possession due {prop.possession}",
        }
        claim = Claim(
            statement=statements[field],
            property_id=prop.id,
            evidence_field=field,
            claimed_value=value if not hasattr(value, "value") else value.value,
        )
        return sentences[field], claim
