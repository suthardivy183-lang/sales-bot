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
| 6 — Orchestrator wired end to end | ⬜ Not started |
| 7 — Hinglish handling | ⬜ Not started |
| 8 — Evaluation suite | ⬜ Not started |
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

**Designed for extension — documented only, deliberately not built for this demo:**

- Invoice generation
- Feedback collection
- Referral tracking
- Renewal / upsell logic
- Standalone analytics dashboard

## Evaluation results

Will be produced by the Task 8 table-driven suite and reported here — a small
hackathon evaluation set, not a production benchmark.

## Demo video

Link will be added at Task 9. No phone numbers or tokens are visible in it.
