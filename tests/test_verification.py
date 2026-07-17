"""Task 4 done-when: the Shela private-pool trap question is correctly refused."""

import pytest

from app.agents.claims import Claim, ClaimVerdict, DraftReply
from app.agents.response import ResponseGenerator
from app.agents.verification import VerificationAgent
from app.nlu.questions import fields_asked_about
from app.properties.repository import PropertyRepository
from app.tools.emi import calculate_emi, quote_for_property_price

TRAP_QUESTION = "Does the Shela property have a private pool?"


@pytest.fixture(scope="module")
def repo() -> PropertyRepository:
    return PropertyRepository()


@pytest.fixture(scope="module")
def verifier(repo) -> VerificationAgent:
    return VerificationAgent(repo)


@pytest.fixture(scope="module")
def generator() -> ResponseGenerator:
    return ResponseGenerator()


class TestTrapQuestion:
    def test_shela_pool_question_is_refused_not_confirmed(
        self, repo, verifier, generator
    ):
        fields = fields_asked_about(TRAP_QUESTION)
        assert fields == ["private_pool"]

        shela = repo.get(2)
        draft = generator.field_answer_reply(shela, fields)
        # The draft is deliberately assertive — proof the gate does the work.
        assert "yes" in draft.text.lower()

        result = verifier.verify(draft)
        assert result.approved is False
        assert result.escalate is True
        assert "can't confirm" in result.text
        assert "private pool" in result.text
        assert "yes" not in result.text.lower()

    def test_no_property_record_supports_a_pool_claim(self, repo, verifier):
        for prop in repo.all():
            claim = Claim(
                statement="a private pool",
                property_id=prop.id,
                evidence_field="private_pool",
                claimed_value=True,
            )
            result = verifier.verify(DraftReply(text="Yes!", claims=(claim,)))
            assert result.approved is False
            assert result.escalate is True


class TestVerdicts:
    def make_claim(self, **overrides) -> Claim:
        values = {
            "statement": "priced at ₹95 lakh",
            "property_id": 2,
            "evidence_field": "price",
            "claimed_value": 9_500_000,
        }
        return Claim(**{**values, **overrides})

    def test_matching_claim_is_supported(self, verifier):
        result = verifier.verify(DraftReply(text="ok", claims=(self.make_claim(),)))
        assert result.checked[0].verdict == ClaimVerdict.SUPPORTED
        assert result.approved is True

    def test_wrong_value_is_contradicted(self, verifier):
        claim = self.make_claim(claimed_value=9_000_000)
        result = verifier.verify(DraftReply(text="ok", claims=(claim,)))
        assert result.checked[0].verdict == ClaimVerdict.CONTRADICTED
        assert result.checked[0].actual_value == 9_500_000

    def test_unknown_property_is_unsupported(self, verifier):
        claim = self.make_claim(property_id=99)
        result = verifier.verify(DraftReply(text="ok", claims=(claim,)))
        assert result.checked[0].verdict == ClaimVerdict.UNSUPPORTED

    def test_missing_field_is_unsupported(self, verifier):
        claim = self.make_claim(evidence_field="private_pool", claimed_value=True)
        result = verifier.verify(DraftReply(text="ok", claims=(claim,)))
        assert result.checked[0].verdict == ClaimVerdict.UNSUPPORTED

    def test_empty_field_is_unsupported_not_guessed(self, verifier):
        # Property #4 is ready-to-move: its possession field is empty.
        claim = Claim(
            statement="possession due 2027-01",
            property_id=4,
            evidence_field="possession",
            claimed_value="2027-01",
        )
        result = verifier.verify(DraftReply(text="ok", claims=(claim,)))
        assert result.checked[0].verdict == ClaimVerdict.UNSUPPORTED


class TestConservativeRewrite:
    def test_contradicted_price_is_corrected_from_the_record(self, verifier):
        wrong_price = Claim(
            statement="priced at ₹90 lakh",
            property_id=2,
            evidence_field="price",
            claimed_value=9_000_000,
        )
        result = verifier.verify(
            DraftReply(text="It costs ₹90 lakh.", claims=(wrong_price,))
        )

        assert result.approved is False
        assert result.escalate is False  # the record had the answer; no human needed
        assert "Correction: the listed price is ₹95 lakh." in result.text

    def test_supported_facts_survive_a_partial_refusal(self, verifier, generator, repo):
        # Ask about possession AND a pool on Shela: possession is evidenced,
        # the pool is not — the reply must keep one and refuse the other.
        draft = generator.field_answer_reply(
            repo.get(2), ["possession", "private_pool"]
        )
        result = verifier.verify(draft)

        assert result.approved is False
        assert result.escalate is True
        assert "can't confirm" in result.text
        assert "private pool" in result.text
        assert "possession due 2026-12" in result.text


class TestEMIVerification:
    def test_correct_quote_is_approved(self, verifier, generator, repo):
        prop = repo.get(4)
        draft = generator.emi_reply(prop, quote_for_property_price(prop.price))
        result = verifier.verify(draft)
        assert result.approved is True

    def test_tampered_emi_is_recomputed_and_corrected(self, verifier, generator, repo):
        prop = repo.get(4)
        honest = quote_for_property_price(prop.price)
        tampered = honest.model_copy(update={"monthly_emi": honest.monthly_emi + 500})

        result = verifier.verify(generator.emi_reply(prop, tampered))
        assert result.approved is False
        assert result.emi_corrected is True
        assert f"₹{honest.monthly_emi:,}/month" in result.text

    def test_hand_verified_quote_used_by_the_demo(self):
        quote = calculate_emi(6_800_000, 8.5, 240)
        assert quote.monthly_emi == 59_012


class TestGeneratorClaimsAreEvidenceLinked:
    def test_property_summaries_pass_verification_unchanged(
        self, verifier, generator, repo
    ):
        draft = generator.properties_reply(list(repo.all()))
        result = verifier.verify(draft)

        assert result.approved is True
        assert result.text == draft.text
        assert len(result.checked) >= 4 * len(repo.all())

    def test_every_claim_names_a_real_property_and_field(self, generator, repo):
        draft = generator.properties_reply(list(repo.all()))
        for claim in draft.claims:
            assert repo.get(claim.property_id) is not None
            assert claim.evidence_field

    def test_known_field_answers_are_approved(self, verifier, generator, repo):
        draft = generator.field_answer_reply(repo.get(2), ["price", "possession"])
        result = verifier.verify(draft)
        assert result.approved is True
        assert "₹95 lakh" in result.text


class TestQuestionDetection:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Does it have a swimming pool?", ["private_pool"]),
            ("Is there a gym and parking?", ["gym", "parking"]),
            ("How much does it cost?", ["price"]),
            ("When will it be ready?", ["possession", "status"]),
            ("What about possession?", ["possession", "status"]),
            ("Looks good, thanks!", []),
        ],
    )
    def test_fields_detected(self, text, expected):
        assert fields_asked_about(text) == expected
