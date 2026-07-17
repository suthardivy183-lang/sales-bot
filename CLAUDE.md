# Build brief: Sales Copilot for FlowZint AI Hackathon 2026

Real estate (Ahmedabad) is the demo vertical — swap the fixtures in Task 2 if another vertical is picked; everything else still applies.

## Working protocol — follow this for the entire session

- Work through the tasks below **one at a time, in order**.
- After finishing each task: stop, summarize what changed, show the key diffs or new files, and ask **"Ready for me to commit and push this?"**
- git status, git diff, tests, formatters, and linters may run freely without asking — those are read-only.
- Do NOT stage, commit, push, or rewrite git history without an explicit yes, given in response to that question.
- Never commit API keys, tokens, .env files, or real phone numbers. .gitignore for secrets is set up in Task 0A, before anything else touches the repo.
- Every task ships with an automated test — a task isn't done because it worked once by hand.
- If a task turns out bigger than it looks once in it, stop and say so — propose splitting it rather than pushing through silently.
- If blocked (missing key, unclear requirement, ambiguous fixture), stop and ask rather than guessing and moving on.
- Track the task list throughout so both sides know where we are.

## Non-negotiable engineering rules

1. Maintain multi-turn conversation state keyed by WhatsApp number. Never treat a message as an isolated request.
2. Deterministic structured filtering (budget, locality, BHK, possession) comes first. Semantic search may rerank, never replace, the hard filters.
3. Every factual property claim must be linked to a property ID and source field. The Verification Agent blocks any claim without matching evidence before it's sent.
4. Don't rely solely on one LLM asking another LLM whether an answer hallucinated. Check structured facts deterministically wherever possible.
5. EMI calculation, CRM writes, slot availability, and bookings are tools, not agents. LLMs don't do financial arithmetic or invent tool results.
6. Every action tool is idempotent — reprocessing the same WhatsApp message ID must never create a duplicate CRM row or booking.
7. Every task ships with an automated test. Working once by hand isn't done.
8. Never log secrets or full phone numbers. Mask PII in logs, screenshots, and the demo video.
9. Prefer a smaller, fully-working system over more architecture boxes. Don't add an agent unless it does real, testable reasoning.
10. Keep the README's Implemented / Designed-for-extension split accurate throughout the build, not just at the end.

## Mission

FlowZint AI Hackathon 2026 (flowzint.in/2026/ai/hackothon/), **Sales Bot** track. Judging weights: Model Innovation & Novelty 30%, Real-World Applicability 25%, Technical Architecture 25%, Documentation Clarity 20%. The organizers explicitly warn entrants away from "generic LLM wrappers". The repo must be **public** and a public demo video is mandatory; incomplete details or private links cause automatic rejection.

## What we're building

An agentic sales system for WhatsApp — not a chatbot, a small team of cooperating agents and tools with a real verification step — built and demoed against **one vertical done well: residential real estate in Ahmedabad.**

Demo scenario, genuinely multi-turn: a customer messages "I want a flat in Ahmedabad." The bot asks for budget, then locality, then BHK — across separate messages, merging each answer into one running picture of the lead. It matches properties, calculates EMI on request, catches itself when asked something it can't verify, books a viewing slot, and writes the outcome to a live CRM sheet.

## Stack (locked)

- **Backend**: Python + FastAPI
- **Validation**: Pydantic
- **Tests**: pytest
- **Session storage**: SQLite
- **Property data**: local JSON (see fixtures below)
- **HTTP client**: httpx
- **LLM**: a provider interface with one configured implementation to start — free-tier model (Gemini or Sarvam for Indic/Hinglish strength). Confirm current free-tier terms before relying on them.
- **CRM**: Google Sheets
- **Deployment**: one host, whichever gets a public demo URL fastest

Build provider abstractions where they cost little, but only one WhatsApp provider and one LLM provider need to actually work for the hackathon.

## Architecture

```text
Customer (WhatsApp)
  -> Gateway (WhatsApp Cloud API / sandbox)
    -> Conversation State (SQLite, keyed by WhatsApp number)
    -> Orchestrator Agent (plans and routes each turn using current state)
       -> Qualification Agent   (extracts intent, budget, locality, BHK, timeline; merges into state across turns)
       -> Property Search Tool  (deterministic filter on BHK/locality/price/possession; optional semantic rerank for fuzzy preferences only)
       -> Pricing / EMI Tool    (deterministic calculator, not LLM math)
       -> Response Generator    (drafts a reply plus a structured claims list, each tagged with property ID + source field)
       -> Verification Agent    (checks each claim against the source record; blocks or escalates unsupported ones)
    -> Action Tools (idempotent CRM row + calendar slot booking, via Sheets)
    -> back to WhatsApp
```

The **Verification Agent is the single most important piece**. The Response Generator must output claims in a structured form, e.g. `{"claim": "3BHK", "property_id": 2, "evidence_field": "bhk"}`, and the verifier checks each one deterministically against that field. If a claim has no matching evidence field, it never goes out as stated — the reply gets rewritten conservatively or flagged for human escalation. Free-text claims that can't be field-checked (e.g. "great for families") may go through an LLM judgment step, but every structured factual claim is checked deterministically first.

## Scope — build this, document the rest

**Build for the live demo (Tasks 0A–6 are the critical path — get these rock solid first):** Conversation state, Qualification Agent, Property Search Tool, Pricing/EMI Tool, evidence-linked Verification Agent, idempotent Action Tools, Response Generator, the full WhatsApp round trip.

**Layer in once the core is solid (Tasks 7–9):** Hinglish handling, a real evaluation suite, documentation and demo polish.

**Optional, only if everything else is done (Task 10):** Small-model cost routing. Skip entirely if it puts anything else at risk.

**Do NOT build — document only, as "designed for extension, not built for this demo":** Invoice generation, feedback collection, referral tracking, renewal/upsell logic, a standalone analytics dashboard.

## Demo fixtures — use these exact five so the trap question works

```json
[
  {"id": 1, "bhk": 2, "locality": "Bopal", "price": 6500000, "status": "ready_to_move"},
  {"id": 2, "bhk": 3, "locality": "Shela", "price": 9500000, "status": "under_construction", "possession": "2026-12"},
  {"id": 3, "bhk": 2, "locality": "Satellite", "price": 11000000, "status": "ready_to_move"},
  {"id": 4, "bhk": 3, "locality": "Bopal", "price": 8500000, "status": "ready_to_move"},
  {"id": 5, "bhk": 4, "locality": "SG Highway", "price": 18000000, "status": "ready_to_move"}
]
```

No `private_pool` field exists on any record — deliberate. The **trap question for the demo**: *"Does the Shela property have a private pool?"* The Verification Agent must catch that this claim has no evidence field and must NOT confirm a pool exists. Build and test against this exact case.

## Task breakdown

- **Task 0A — Local scaffold.** Repo structure; .gitignore for secrets; .env.example; a local webhook endpoint that accepts a mocked WhatsApp payload and returns a hardcoded reply; an automated test posting that mock payload. *Done when:* a test posts a fake WhatsApp message locally and gets a reply back — no real WhatsApp account involved yet.
- **Task 0B — Real WhatsApp transport.** Connect a provider (Meta Cloud API test number, Twilio Sandbox, or 360dialog sandbox — fastest wins); configure the public webhook URL; validate incoming payloads; send a real outbound reply; write down setup steps for the README. *Done when:* a real WhatsApp message round-trips end to end.
- **Task 1 — Conversation state + Qualification Agent.** Session state keyed by WhatsApp number, in SQLite: `{session_id, intent, locality, budget_min, budget_max, bhk, timeline, selected_property_id, stage}`. The Qualification Agent reads and updates this state each turn, merging new information. *Done when:* a simulated 4-message conversation (budget in one message, locality in the next) ends with a fully populated, correct state object.
- **Task 2 — Property Search Tool (hybrid retrieval).** Deterministic filtering first — BHK, locality, price ceiling, possession status. Semantic reranking only for unstructured preferences, applied to already-filtered candidates. *Done when:* "2BHK in Bopal under 70 lakh" returns exactly property #1 and nothing else.
- **Task 3 — Pricing/EMI Tool.** Pure function: principal, rate, tenure -> EMI, standard amortization formula, no LLM. *Done when:* a unit test matches a hand-calculated EMI value.
- **Task 4 — Evidence-linked response + Verification Agent.** Response Generator outputs draft reply + structured claims list tagged with property ID and source field. Verification Agent checks each structured claim deterministically; free-text claims may get an LLM judgment pass. Unsupported claims are rewritten conservatively or escalated. *Done when:* the Shela pool trap question is correctly refused.
- **Task 5 — Idempotent action tools.** CRM row write and slot booking, keyed by WhatsApp message ID. *Done when:* replaying the same incoming message twice produces exactly one CRM row and one booking.
- **Task 6 — Wire it end to end.** Orchestrator ties Tasks 1–5 into the full live flow; verification always runs before anything is sent. *Done when:* the full Ahmedabad scenario runs live, unassisted, including the trap question.
- **Task 7 — Hinglish handling.** Detect code-switched input; confirm Qualification + Search don't degrade. *Done when:* mixed-language budget phrasing still extracts and filters correctly.
- **Task 8 — Evaluation suite.** One table-driven test file (fixtures + expected outcomes) covering: qualification extraction, multi-turn state merging, exact property matching, no-match cases, unsupported-amenity claims, incorrect price claims, EMI accuracy, Hinglish, ambiguous requests, booking duplication, human-handoff triggers. Report a pass-rate table in the README, labeled as a small hackathon evaluation set. *Done when:* the suite runs in one command and produces a results table.
- **Task 9 — Docs and demo polish.** README with architecture diagram, setup steps, implemented-vs-roadmap split, eval results table, demo video link. Demo script: greeting -> qualification across turns -> property match -> EMI calc -> trap question caught live -> booking -> sheet updating on screen. Mask phone numbers and tokens everywhere. *Done when:* a stranger could read the README and know exactly what's real versus planned.
- **Task 10 — Small-model routing (optional).** Cheap model for easy turns, stronger model for ambiguous ones. Skip entirely if it risks Tasks 0–9.

### Evaluation targets (report actuals, not guarantees)

| Metric | Target |
| --- | --- |
| Qualification field accuracy | ≥90% |
| Property top-1 retrieval accuracy | ≥90% |
| Unsupported-claim blocking | 100% on test set |
| EMI calculation pass rate | 100% |
| Booking workflow success | 100% |
| Hinglish extraction accuracy | ≥85% |

## Documentation requirements (Documentation Clarity, 20%)

- README covers: what this is, the architecture diagram, setup steps, built-vs-roadmap split, the eval table, and a link to the demo video.
- Repo must be **public** before submission — verify explicitly.
- Demo video: 2–3 minutes, public, must include the trap-question moment, no visible phone numbers or tokens.

## If a judge asks "why does this matter, Interakt/Haptik already do this?"

The market already proves the problem is worth solving — Salesforce signed a definitive agreement in June 2026 to acquire Fin (formerly Intercom) for roughly $3.6B. Production data shows even funded platforms resolve complex queries only 15–30% of the time, mostly because nothing catches the model when it's confidently wrong. That's the specific gap this architecture closes — not a from-scratch competitor to Interakt, a proof of the missing piece.
