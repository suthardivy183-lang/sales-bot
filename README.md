# Sales Copilot — WhatsApp Agentic Sales System

Entry for **FlowZint AI Hackathon 2026, Sales Bot track**. An agentic sales system
for WhatsApp — a small team of cooperating agents and deterministic tools with a
real verification step — demoed against one vertical done well: **residential real
estate in Ahmedabad**.

The differentiator is the **Verification Agent**: every factual property claim in a
draft reply is tagged with a property ID and source field, then checked
deterministically against the property record before anything is sent. A claim
without evidence never goes out as stated.

## Architecture

```text
Customer (WhatsApp)
  -> Gateway (WhatsApp Cloud API)
    -> Conversation State (SQLite, keyed by WhatsApp number)
    -> Orchestrator Agent (plans and routes each turn using current state)
       -> Qualification Agent   (extracts intent, budget, locality, BHK, timeline)
       -> Property Search Tool  (deterministic filters; semantic rerank for fuzzy prefs only)
       -> Pricing / EMI Tool    (deterministic calculator, not LLM math)
       -> Response Generator    (draft reply + structured claims list)
       -> Verification Agent    (checks every claim against the source record)
    -> Action Tools (idempotent CRM row + viewing slot booking, via Google Sheets)
    -> back to WhatsApp
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your own values; never commit .env

# Run the API
uvicorn app.main:app --reload

# Run the tests
pytest
```

## Build progress

| Task | Status |
| --- | --- |
| 0A — Local scaffold, mocked WhatsApp webhook + tests | ✅ Done |
| 0B — Real WhatsApp transport | ⬜ Not started |
| 1 — Conversation state + Qualification Agent | ✅ Done |
| 2 — Property Search Tool (hybrid retrieval) | ✅ Done |
| 3 — Pricing/EMI Tool | ✅ Done |
| 4 — Evidence-linked response + Verification Agent | ✅ Done |
| 5 — Idempotent action tools (CRM + booking) | ✅ Done |
| 6 — Orchestrator wired end to end | ✅ Done |
| 7 — Hinglish handling | ✅ Done |
| 8 — Evaluation suite | ✅ Done |
| 9 — Docs + demo video | ⬜ Not started |
| 10 — Small-model routing (optional) | ⬜ Not started |

## Implemented vs. designed for extension

**Implemented (working, tested):**

- FastAPI webhook that validates WhatsApp Cloud API payloads (mocked for now),
  acknowledges status receipts, and returns a reply — with PII masking so full
  phone numbers never appear in logs or responses.
- Multi-turn conversation state in SQLite, keyed by WhatsApp number — every
  turn merges into one running picture of the lead; nothing is treated as an
  isolated request.
- Qualification Agent with **rules-first hybrid extraction**: Indian budget
  formats (`70 lakh`, `1.2 cr`, `60–80 lakh`, `₹65,00,000`), BHK, locality,
  intent, and timeline are parsed deterministically; an optional Gemini pass
  fills only the fields rules couldn't parse and can never override them.
  Provider failures degrade gracefully to rules-only extraction.
- Property Search Tool with **hybrid retrieval**: deterministic hard filters
  (BHK, locality, price ceiling, possession status) over the five Ahmedabad
  fixtures run first; a preference reranker ("ready soon", "family-friendly",
  "sasta") may only reorder the filtered candidates — it can never add a
  property back or drop one. Reranking is keyword-heuristic for the demo; an
  embedding reranker slots in behind the same signature (see roadmap).
- Pricing/EMI Tool: pure reducing-balance amortization (`EMI = P·r·(1+r)^n /
  ((1+r)^n − 1)`) verified against hand-calculated values — no LLM ever does
  financial arithmetic. Default assumptions (8.5% p.a., 20 years, 20% down)
  are part of the quote object so replies must state them.
- **Evidence-linked generation + deterministic verification** (the core of
  this entry): every factual statement in a draft reply carries a structured
  claim `{property_id, evidence_field, claimed_value}`. The Verification Agent
  checks each claim against the property record before anything is sent —
  supported claims ship, contradicted claims are rewritten with the record's
  actual value, unsupported claims (like the private-pool trap question) are
  refused outright and escalated to a human. EMI numbers are re-computed from
  their own inputs, so a tampered or invented figure is corrected
  deterministically. LLM-judged soft claims ("great for families") are a
  designed extension, deliberately not built.
- **Idempotent action tools**: CRM lead writes and viewing-slot bookings are
  keyed by WhatsApp message ID through an action ledger — a replayed webhook
  event returns the original result instead of re-executing, so duplicates are
  structurally impossible (a PRIMARY KEY on the slot also rules out
  double-booking). Two CRM backends behind one protocol: SQLite (local) and
  Google Sheets (live demo sheet, REST). CRM rows and bookings store masked
  phone numbers only, so the on-screen sheet in the demo can never leak PII.
- **Orchestrator wired end to end**: each turn routes to booking, EMI,
  property questions, or qualification based on intent and stage; the
  verification gate runs before every reply that carries property facts. The
  complete demo scenario — greeting → multi-turn qualification → verified
  match → EMI → trap question refused → booking → CRM rows — runs as one
  automated end-to-end test through the webhook, including a webhook replay
  that changes nothing.
- **Hinglish handling**: code-switch detection (romanized markers +
  Devanagari script) plus native rule coverage for common Hinglish phrasings —
  "70 lakh tak", "80 lakh ke andar", "1 cr se kam", "50 lakh se upar",
  "3 kamre", "ghar lena hai", "turant", "2 mahine mein" — verified by a full
  Hinglish conversation running end to end to a verified match. Devanagari
  *extraction* relies on the LLM pass (rules cover romanized input), which is
  a documented limitation without an API key, never silently wrong output.

**Designed for extension — documented only, deliberately not built for this demo:**

- Invoice generation
- Feedback collection
- Referral tracking
- Renewal / upsell logic
- Standalone analytics dashboard

## Evaluation results

One table-driven suite ([evals/cases.json](evals/cases.json), 58 cases), run
with a single command:

```bash
python -m evals.run_evals
```

This is a **small hackathon evaluation set, not a production benchmark**. Two
cases are deliberately known-hard (word-number budgets like "seventy five
lakh", and Devanagari-only script without an LLM key) so the rates below are
honest, not curated. Every case runs against the real production components —
no mocks. The same targets are enforced as a CI gate in
[tests/test_evals.py](tests/test_evals.py).

| Category | Passed | Total | Rate | Target | Status |
| --- | --- | --- | --- | --- | --- |
| qualification | 9 | 10 | 90.0% | ≥90% | ✅ |
| state_merging | 4 | 4 | 100.0% | ≥100% | ✅ |
| retrieval | 8 | 8 | 100.0% | ≥90% | ✅ |
| no_match | 4 | 4 | 100.0% | ≥100% | ✅ |
| unsupported_claim | 6 | 6 | 100.0% | ≥100% | ✅ |
| price_claim | 4 | 4 | 100.0% | ≥100% | ✅ |
| emi | 5 | 5 | 100.0% | ≥100% | ✅ |
| hinglish | 7 | 8 | 87.5% | ≥85% | ✅ |
| ambiguous | 4 | 4 | 100.0% | ≥100% | ✅ |
| booking_duplication | 2 | 2 | 100.0% | ≥100% | ✅ |
| handoff | 3 | 3 | 100.0% | ≥100% | ✅ |
| **Overall** | **56** | **58** | **96.6%** | — | — |

## Demo video

Link will be added at Task 9. No phone numbers or tokens are visible in it.
