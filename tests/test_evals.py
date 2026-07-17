"""Task 8 done-when: the eval suite runs in one command and meets its targets.

The suite itself lives in evals/ (table-driven cases + runner); this wrapper
makes every category target a CI gate.
"""

from evals.run_evals import run_all, summarize


def test_every_category_meets_its_target():
    summaries = summarize(run_all())
    misses = [
        f"{s.category}: {s.rate:.1f}% < target {s.target:.0f}%"
        for s in summaries
        if not s.met
    ]
    assert not misses, misses


def test_the_suite_actually_ran_everything():
    results = run_all()
    assert len(results) >= 50
    assert {r.category for r in results} == {
        "qualification",
        "state_merging",
        "retrieval",
        "no_match",
        "unsupported_claim",
        "price_claim",
        "emi",
        "hinglish",
        "ambiguous",
        "booking_duplication",
        "handoff",
    }
