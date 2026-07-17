# Demo run sheet — 2–3 minutes, unassisted

The exact live sequence, verified continuously by the automated end-to-end
test (`tests/test_orchestrator.py::TestFullAhmedabadScenario`). If the test is
green, this script works.

## Two ways to run the demo

- **WhatsApp (real channel):** needs Task 0B credentials wired; record the
  WhatsApp chat with the number masked.
- **Browser chat simulator (no credentials needed):** run `uvicorn app.main:app`
  and open `http://localhost:8000/`. It posts to the same `/webhook`, so the
  orchestrator, verification, and CRM are identical. The quick-prompt chips
  follow this exact script; the trap chip is highlighted. Use this if Task 0B
  isn't wired yet — just show the "Local simulator" label on screen so it's
  clearly not passed off as live WhatsApp.

## Pre-flight checklist

- [ ] Fresh session: click **↻ New conversation** (simulator) or delete
      `sessions.db` so the lead starts from scratch
- [ ] Server running; WhatsApp webhook reachable (Task 0B) **or** the browser
      simulator open at `/`
- [ ] CRM sheet visible on screen, empty
- [ ] **Masking check**: phone number hidden in the WhatsApp client UI or
      blurred in post; no `.env`, tokens, or API consoles on screen
- [ ] Screen recorder on; keep the WhatsApp chat + CRM sheet both visible

## Cast on screen

1. WhatsApp chat (customer side) — number masked
2. CRM sheet — rows will appear live; it stores masked numbers by design
3. (Optional) server log pane — it logs masked numbers only

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

## Suggested narration beats (~20s total talking)

- After 4: "Three separate messages merged into one qualified lead — state,
  not prompt tricks."
- At 6: "The generator actually drafted a confident yes here. The verifier
  found no evidence field for a pool and refused it — that's the piece
  production sales bots are missing."
- After 7: "Every action is idempotent by message ID — WhatsApp redeliveries
  can't double-book or duplicate CRM rows."

## Reset between takes

```bash
rm -f sessions.db          # clears state, ledger, local CRM, bookings
```

Clear the sheet rows manually if using the Google Sheets backend.

## Recording rules (non-negotiable)

- No real phone numbers anywhere — mask in the client, blur in post if needed
- No tokens, `.env` contents, or cloud consoles on screen
- Video must be public and 2–3 minutes; the trap moment must be included
