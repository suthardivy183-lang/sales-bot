"""Task 8 evaluation suite — table-driven, one command:  python -m evals.run_evals

Every case in cases.json runs against the REAL production components (no
mocks). This is a small hackathon evaluation set, not a production benchmark;
two cases are deliberately known-hard so the rates below are honest, not
curated. Exit code is non-zero if any category misses its target.
"""

import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.actions.booking import BookingTool
from app.actions.crm import CrmTool, SqliteCrmBackend
from app.actions.ledger import ActionLedger
from app.agents.qualification import QualificationAgent, next_question
from app.agents.response import ResponseGenerator
from app.agents.verification import VerificationAgent
from app.agents.claims import Claim, ClaimVerdict, DraftReply
from app.config import Settings
from app.deps import build_orchestrator
from app.gateway.schemas import IncomingMessage
from app.nlu.hybrid import HybridExtractor
from app.nlu.questions import fields_asked_about
from app.nlu.routing import ModelRouter
from app.nlu.rules import extract_fields
from app.properties.repository import PropertyRepository
from app.state.models import SessionState
from app.state.store import SessionStore
from app.tools.emi import calculate_emi
from app.tools.property_search import criteria_from_state, search

CASES_PATH = Path(__file__).parent / "cases.json"

TARGETS = {
    "qualification": 90.0,
    "state_merging": 100.0,
    "retrieval": 90.0,
    "no_match": 100.0,
    "unsupported_claim": 100.0,
    "price_claim": 100.0,
    "emi": 100.0,
    "hinglish": 85.0,
    "ambiguous": 100.0,
    "booking_duplication": 100.0,
    "handoff": 100.0,
    "routing": 100.0,
}

_PROFILE_FIELDS = ("intent", "locality", "budget_min", "budget_max", "bhk", "timeline")

_REPO = PropertyRepository()
_VERIFIER = VerificationAgent(_REPO)
_GENERATOR = ResponseGenerator()


@dataclass
class EvalResult:
    category: str
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CategorySummary:
    category: str
    passed: int
    total: int
    target: float
    rate: float = field(init=False)
    met: bool = field(init=False)

    def __post_init__(self):
        self.rate = 100.0 * self.passed / self.total if self.total else 0.0
        self.met = self.rate >= self.target


def _fields_match(actual_model, expected: dict) -> str:
    """Empty string when every expected field matches; else a diff detail."""
    diffs = []
    for key, want in expected.items():
        got = getattr(actual_model, key)
        if want is None:
            if got is not None:
                diffs.append(f"{key}: expected None, got {got!r}")
        elif got is None or str(got) != str(want):
            diffs.append(f"{key}: expected {want!r}, got {got!r}")
    return "; ".join(diffs)


def _eval_extraction(case: dict) -> EvalResult:
    detail = _fields_match(extract_fields(case["message"]), case["expected"])
    return EvalResult(case["category"], case["name"], not detail, detail)


def _eval_state_merging(case: dict) -> EvalResult:
    with tempfile.TemporaryDirectory() as tmp:
        store = SessionStore(Path(tmp) / "eval.db")
        agent = QualificationAgent(HybridExtractor())
        for text in case["messages"]:
            state = store.get_or_create("919999000011")
            store.save(agent.process_turn(state, text))
        final = store.get("919999000011")
    detail = _fields_match(final, case["expected"])
    return EvalResult(case["category"], case["name"], not detail, detail)


def _eval_retrieval(case: dict) -> EvalResult:
    fields = extract_fields(case["message"])
    state = SessionState(
        session_id="eval",
        wa_id="eval",
        bhk=fields.bhk,
        locality=fields.locality,
        budget_max=fields.budget_max,
        timeline=fields.timeline,
    )
    results = search(_REPO.all(), criteria_from_state(state), case["message"])
    got = [prop.id for prop in results]
    passed = got == case["expected_ids"]
    detail = "" if passed else f"expected {case['expected_ids']}, got {got}"
    return EvalResult(case["category"], case["name"], passed, detail)


def _eval_unsupported_claim(case: dict) -> EvalResult:
    prop = _REPO.get(case["property_id"])
    fields = fields_asked_about(case["question"])
    draft = _GENERATOR.field_answer_reply(prop, fields)
    verdict = _VERIFIER.verify(draft)
    passed = (
        not verdict.approved
        and verdict.escalate
        and "can't confirm" in verdict.text
        and "yes" not in verdict.text.lower()
    )
    detail = "" if passed else f"approved={verdict.approved} text={verdict.text!r}"
    return EvalResult(case["category"], case["name"], passed, detail)


def _eval_price_claim(case: dict) -> EvalResult:
    claim = Claim(
        statement="quoted price",
        property_id=case["property_id"],
        evidence_field="price",
        claimed_value=case["claimed_price"],
    )
    verdict = _VERIFIER.verify(DraftReply(text="draft", claims=(claim,)))
    passed = (
        not verdict.approved
        and not verdict.escalate
        and verdict.checked[0].verdict == ClaimVerdict.CONTRADICTED
        and case["expected_correction"] in verdict.text
    )
    detail = "" if passed else f"text={verdict.text!r}"
    return EvalResult(case["category"], case["name"], passed, detail)


def _eval_emi(case: dict) -> EvalResult:
    got = calculate_emi(
        case["principal"], case["annual_rate"], case["months"]
    ).monthly_emi
    passed = got == case["expected_emi"]
    detail = "" if passed else f"expected {case['expected_emi']}, got {got}"
    return EvalResult(case["category"], case["name"], passed, detail)


def _eval_ambiguous(case: dict) -> EvalResult:
    agent = QualificationAgent(HybridExtractor())
    state = SessionState(session_id="eval", wa_id="eval")
    new_state = agent.process_turn(state, case["message"])
    extracted_noise = [
        f for f in _PROFILE_FIELDS if getattr(new_state, f) is not None
    ]
    question = next_question(new_state)
    passed = not extracted_noise and question is not None
    detail = "" if passed else f"noise={extracted_noise} question={question!r}"
    return EvalResult(case["category"], case["name"], passed, detail)


def _eval_booking_duplication(case: dict) -> EvalResult:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "eval.db"
        ledger = ActionLedger(db)
        if case["variant"] == "booking":
            tool = BookingTool(db, ledger)
            first = tool.book("wamid.dup", "919999000011")
            replay = tool.book("wamid.dup", "919999000011")
            passed = (
                first.created
                and not replay.created
                and first.slot_id == replay.slot_id
                and len(tool.available_slots()) == 3
            )
            detail = "" if passed else f"first={first} replay={replay}"
        else:
            backend = SqliteCrmBackend(db)
            crm = CrmTool(backend, ledger)
            state = SessionState(session_id="eval", wa_id="919999000011")
            crm.write_lead("wamid.dup", state, note="eval")
            replay = crm.write_lead("wamid.dup", state, note="eval")
            rows = len(backend.all_leads())
            passed = not replay.created and rows == 1
            detail = "" if passed else f"rows={rows} replay_created={replay.created}"
    return EvalResult(case["category"], case["name"], passed, detail)


def _eval_handoff(case: dict) -> EvalResult:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "eval.db"
        settings = Settings(database_path=str(db), _env_file=None)
        orchestrator = build_orchestrator(settings)
        if case.get("pre_book_all"):
            tool = BookingTool(db, ActionLedger(db))
            for i in range(4):
                tool.book(f"wamid.pre{i}", f"91800000000{i}")
        for i, text in enumerate(case["setup"]):
            orchestrator.handle_message(
                IncomingMessage(
                    wa_id="919999000011",
                    message_id=f"wamid.setup{i}",
                    text=text,
                    timestamp="0",
                )
            )
        reply = orchestrator.handle_message(
            IncomingMessage(
                wa_id="919999000011",
                message_id="wamid.question",
                text=case["question"],
                timestamp="0",
            )
        )
        notes = [lead.note for lead in SqliteCrmBackend(db).all_leads()]
    passed = case["expect_reply_contains"] in reply and any(
        note.startswith(case["expect_note_prefix"]) for note in notes
    )
    detail = "" if passed else f"reply={reply!r} notes={notes}"
    return EvalResult(case["category"], case["name"], passed, detail)


_ROUTER = ModelRouter(small_model="small", large_model="large")


def _eval_routing(case: dict) -> EvalResult:
    got = _ROUTER.decide(case["message"]).tier.value
    passed = got == case["expected_tier"]
    detail = "" if passed else f"expected {case['expected_tier']}, got {got}"
    return EvalResult(case["category"], case["name"], passed, detail)


_EXECUTORS = {
    "qualification": _eval_extraction,
    "routing": _eval_routing,
    "hinglish": _eval_extraction,
    "state_merging": _eval_state_merging,
    "retrieval": _eval_retrieval,
    "no_match": _eval_retrieval,
    "unsupported_claim": _eval_unsupported_claim,
    "price_claim": _eval_price_claim,
    "emi": _eval_emi,
    "ambiguous": _eval_ambiguous,
    "booking_duplication": _eval_booking_duplication,
    "handoff": _eval_handoff,
}


def run_all() -> list[EvalResult]:
    cases = json.loads(CASES_PATH.read_text())
    return [_EXECUTORS[case["category"]](case) for case in cases]


def summarize(results: list[EvalResult]) -> list[CategorySummary]:
    return [
        CategorySummary(
            category=category,
            passed=sum(r.passed for r in results if r.category == category),
            total=sum(1 for r in results if r.category == category),
            target=target,
        )
        for category, target in TARGETS.items()
    ]


def print_report(results: list[EvalResult]) -> bool:
    summaries = summarize(results)
    print("| Category | Passed | Total | Rate | Target | Status |")
    print("| --- | --- | --- | --- | --- | --- |")
    for s in summaries:
        status = "✅" if s.met else "❌"
        print(
            f"| {s.category} | {s.passed} | {s.total} "
            f"| {s.rate:.1f}% | ≥{s.target:.0f}% | {status} |"
        )
    total_passed = sum(r.passed for r in results)
    print(
        f"| **Overall** | {total_passed} | {len(results)} "
        f"| {100.0 * total_passed / len(results):.1f}% | — | — |"
    )
    failures = [r for r in results if not r.passed]
    if failures:
        print("\nFailed cases:")
        for r in failures:
            print(f"  - [{r.category}] {r.name}: {r.detail}")
    return all(s.met for s in summaries)


def main() -> int:
    return 0 if print_report(run_all()) else 1


if __name__ == "__main__":
    sys.exit(main())
