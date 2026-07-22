# ChatGPT Codex Hackathon demo run sheet — 3 minutes maximum

The exact live sequence, verified continuously by the automated end-to-end
test (`tests/test_orchestrator.py::TestFullAhmedabadScenario`). If the test is
green, this script works.

## Recommended recording path

Record the public browser simulator at
**https://sales-bot-rust.vercel.app**. It posts to the same `/webhook` as the
WhatsApp adapter, so qualification, verification, booking, and CRM behavior
are identical without relying on a phone number or provider credentials during
the submission demo.

The Meta WhatsApp channel and ElevenLabs transcript adapter are implemented
integration paths, but their controlled live checks are pending credentials
and dashboard mapping. Do not represent either as live in the video until that
test is complete.

## Pre-flight checklist

- [ ] Run `pytest` successfully and close any terminal containing secrets
- [ ] Open the public simulator in a fresh browser session
- [ ] Open the public GitHub repository on the commit-history page
- [ ] Open a clean Codex task or prior safe build/test evidence; do not show
      `.env`, provider dashboards, tokens, or full phone numbers
- [ ] **Masking check**: no phone numbers, tokens, API consoles, or private
      browser tabs visible anywhere in the recording
- [ ] Screen recorder on; keep the simulator readable at all times

## Cast on screen

1. Public browser simulator — main end-to-end product flow
2. GitHub commit history — visible proof of incremental implementation
3. Codex build/test view — short evidence of agentic planning, implementation,
   and verification work
4. Optional CRM sheet — only after live Sheets configuration is complete

## Three-minute structure

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:20 | Simulator landing screen | “Sales Copilot is a Hinglish real-estate Domain Agent. It qualifies a lead, searches verified inventory, and refuses unsupported facts.” |
| 0:20–1:45 | Steps 1–5 below | Show stateful qualification, the Bopal match, and deterministic EMI. |
| 1:45–2:25 | Step 6 below | Pause at the unsupported pool answer: “The agent cannot confirm a field that does not exist in the verified property record.” |
| 2:25–2:40 | Step 7 below | Show the booking confirmation and idempotency explanation. |
| 2:40–3:00 | GitHub + Codex evidence | Show commits/tests and explain that Codex was used for planning, implementation, test feedback, and refinement. |

## Script

| # | Customer sends | Expected bot reply (verbatim gist) | Point at |
| --- | --- | --- | --- |
| 1 | Hi, I'm looking to buy a flat in Ahmedabad | Asks for **budget** | Multi-turn state: no re-asking |
| 2 | Under 90 lakh | Asks for **area** (Bopal / Shela / Satellite / SG Highway) | |
| 3 | Bopal side | Asks **how many bedrooms** | |
| 4 | 3BHK please, ready to move | "3BHK in Bopal — ₹85 lakh, ready to move (property #4)" + booking hint | **CRM row 1 appears** (qualified lead, masked number) |
| 5 | What would the EMI be? | "EMI works out to **₹59,012/month**" with 20% down, 8.5% p.a., 20 years stated | Deterministic tool — not LLM math |
| 6 | **Does the Shela property have a private pool?** | "**I can't confirm a private pool from the verified listing data**, so I won't state it as fact. I've flagged this for a human agent…" | **THE MOMENT.** Linger. **CRM row 2: HANDOFF** |
| 7 | Great, book a viewing | "…booked for **Saturday 11:00**. Our agent will meet you there." | **CRM row 3: viewing booked** |

Optional flex if time remains: resend/replay message 7 (same message ID) and
show that nothing duplicates — same slot, same three CRM rows.

## Suggested narration beats

- After 4: "Three separate messages merged into one qualified lead — state,
  not prompt tricks."
- At 6: "The generator actually drafted a confident yes here. The verifier
  found no evidence field for a pool and refused it — that's the piece
  production sales bots are missing."
- After 7: "Every action is idempotent by message ID — webhook redeliveries
  can't double-book or duplicate CRM rows."
- Final 20 seconds: "The repository contains the verification-first
  architecture, a 64-case evaluation set, and automated tests. Codex was used
  as an engineering partner through planning, implementation, and review."

## Reset between takes

```bash
rm -f sessions.db          # clears state, ledger, local CRM, bookings
```

Clear the sheet rows manually if using the Google Sheets backend.

## Recording rules (non-negotiable)

- No real phone numbers anywhere — mask in the client, blur in post if needed
- No tokens, `.env` contents, or cloud consoles on screen
- Video must be public, no more than 3 minutes, and include the trap moment
- Upload the public video, then add its link to `README.md` and `SUBMISSION.md`
