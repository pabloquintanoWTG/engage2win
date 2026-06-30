# CLAUDE.md — Project context for Engage2Win

> This file is read automatically by Claude Code at the start of every session.

## What we are building

**Engage2Win** is an AI-powered analysis tool for e2open / WiseTech Global's
**engage2win sales methodology**. A facilitator or participant uploads a photo of a
thinking map created during an engage2win session — a large sheet covered in
handwritten, color-coded, spatially-arranged sticky notes — and the platform returns
a structured **methodology evaluation**: an overall **Red/Amber/Green verdict**, a RAG
rating across five dimensions, strengths, recommendations, and follow-up questions to
deepen thinking.

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

- Phase 0 (Validation): **done.** 36 real maps analysed via the `claude` CLI backend;
  results reviewed and judged trustworthy. See `validate/`.
- Phase 1 (App): **Lean MVP built** — local Flask web app in `app/` (upload → analyze
  → editable RAG result), e2open-branded, reusing the Phase 0 core. Local-only by
  design; no auth/DB/deploy yet.

## Decisions already made

- **Output shape:** five dimensions `detail, insight, clarity, innovation, rigor`, plus
  an overall verdict, all reported as a **Red/Amber/Green band** (green ≥70, amber 60–69,
  red <60) derived from a 0–100 score the model still produces internally. Also
  `strengths[]`, `recommendations[]`, `questions[]`. See `/validate/schema.json`
  (`verdict.band` ∈ green|amber|red).
- **Context fields:** participant/team name, role/department, methodology area, session
  topic, language. No age or educational stage.
- **Languages:** English default; Spanish and Catalan also supported.
- **Phase 1 MVP stack:** Python + Flask, local only, reusing `validate/run.py` (the
  `claude` CLI backend — no API key). See `app/README.md`.
- **Production stack (deferred, later phase):** Next.js + Supabase + Anthropic Claude
  (vision, via API key) + Vercel. The `claude`-CLI backend cannot run serverless, so the
  deployable path needs an API key — out of scope for the local MVP.

## Hard rules

1. Prove the AI before the app. Do not scaffold UI until the harness shows > 80%.
2. The schema is the contract. Always validate JSON against `/validate/schema.json`.
3. Never commit secrets. API keys live in `.env.local` (gitignored).
4. Never commit map photos. `/samples` is gitignored.
