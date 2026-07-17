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
| 1 — Conversation state + Qualification Agent | ⬜ Not started |
| 2 — Property Search Tool (hybrid retrieval) | ⬜ Not started |
| 3 — Pricing/EMI Tool | ⬜ Not started |
| 4 — Evidence-linked response + Verification Agent | ⬜ Not started |
| 5 — Idempotent action tools (CRM + booking) | ⬜ Not started |
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
