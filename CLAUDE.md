# CLAUDE.md — Project context for Engage2Win

> This file is read automatically by Claude Code at the start of every session.

## What we are building

**Engage2Win** is an AI-powered analysis tool for e2open / WiseTech Global's
**engage2win sales methodology**. A facilitator or participant uploads a photo of a
thinking map created during an engage2win session — a large sheet covered in
handwritten, color-coded, spatially-arranged sticky notes — and the platform returns
a structured **methodology evaluation**: an overall verdict + score, scores across five
dimensions, strengths, recommendations, and follow-up questions to deepen thinking.

The AI core is the same vision model technology proven in MT EDU. The output shape
mirrors MT EDU but is adapted for a business/sales methodology context: no educational
stages, no age-based calibration — just a rigorous assessment of how well the map
captures and applies the engage2win methodology.

## The one thing that matters most

Can a vision model read a messy, handwritten, photographed engage2win map and return
an evaluation a facilitator or manager trusts? Prove this with the validation harness
before building any app.

**Success metric — "edit-not-redo rate":** on what % of real maps is *correcting*
the AI's output faster than redoing it from scratch? **Target: > 80%.**

## Current status

- Phase 0 (Validation): harness ready, awaiting real engage2win map photos in `/samples`.
- Phase 1 (App): not started.

## Decisions already made

- **Output shape:** five dimensions `detail, insight, clarity, innovation, rigor`, an
  overall 0–100 score, a verdict band (high/mid/low), `strengths[]`, `recommendations[]`,
  `questions[]`. See `/validate/schema.json`.
- **Context fields:** participant/team name, role/department, methodology area, session
  topic, language. No age or educational stage.
- **Languages:** English default; Spanish and Catalan also supported.
- **Stack (if app is built):** Next.js + Supabase + Anthropic Claude (vision) + Vercel.

## Hard rules

1. Prove the AI before the app. Do not scaffold UI until the harness shows > 80%.
2. The schema is the contract. Always validate JSON against `/validate/schema.json`.
3. Never commit secrets. API keys live in `.env.local` (gitignored).
4. Never commit map photos. `/samples` is gitignored.
