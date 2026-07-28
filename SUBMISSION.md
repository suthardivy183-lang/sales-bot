# Sales Copilot: a verified Hinglish real-estate sales agent

## Hackathon track

**ChatGPT Codex Hackathon 2026**

Primary track: **Domain Agents**

Secondary fit: **AI for Bharat's Businesses** and **Vernacular / Indic
Languages & Local Discovery**

## Problem

Indian real-estate sales conversations often begin on WhatsApp, in English or
Hinglish, and unfold over several short messages. A conventional chatbot can
answer quickly but may invent property details, lose the qualification context,
or create duplicate CRM and booking records when a webhook is replayed.

## Solution

Sales Copilot is a verification-first sales agent for residential real estate
in Ahmedabad. It maintains one lead profile across turns, extracts budget,
locality, BHK, and timeline, applies deterministic filters to a verified local
inventory, and only sends property facts that are tied to a property ID and a
source field.

The key safety moment is the deliberate trap question: *“Does the Shela
property have a private pool?”* No fixture contains a pool field, so the
Verification Agent refuses to confirm it and creates a human-handoff CRM note.

## Technical implementation

- **Backend:** Python, FastAPI, Pydantic, SQLite, httpx
- **Conversation state:** SQLite, keyed by WhatsApp number
- **Qualification:** deterministic English/Hinglish rules; optional Gemini
  gap-fill that cannot override rule-derived fields
- **Inventory:** JSON fixtures with deterministic BHK, locality, budget, and
  possession filters before preference reranking
- **Safety:** evidence-linked structured claims plus deterministic verification
- **Action tools:** deterministic EMI, idempotent CRM writes, and idempotent
  viewing-slot booking
- **Channels:** public browser simulator, Meta WhatsApp Cloud API adapter, and
  ElevenLabs transcript webhook adapter

## Why it matters

The product is designed for sales teams that need speed without letting an AI
agent make unsupported claims. It supports Hinglish qualification phrases such
as “70 lakh tak,” “2 bhk chahiye,” and “turant,” while preserving a clear
evidence trail for every factual property response.

## Evidence of quality

- 244 automated tests
- 64-case hackathon evaluation set: 63/64 passed (98.4%)
- 100% on the evaluation sets for unsupported-claim blocking, price-claim
  correction, EMI, booking duplication, and human handoff
- Public deployed simulator: https://sales-bot-rust.vercel.app
- Public repository: https://github.com/suthardivy183-lang/sales-bot

## Codex-assisted development

The public commit history documents the incremental build: scaffolding,
conversation state, deterministic retrieval, verification, idempotent actions,
evaluation coverage, voice transport, secure WhatsApp transport, and the
Google Sheets CRM adapter. The demo video will show the implementation and
test-feedback loop in Codex alongside the live product flow.

## Public submission links

- Deployed application: https://sales-bot-rust.vercel.app
- GitHub repository: https://github.com/suthardivy183-lang/sales-bot
- Demo video: TODO — public link required before submission
- Google Doc: TODO — publish this content as an anyone-with-the-link Google Doc
