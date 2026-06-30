# Engage2Win — Phase 1 app (Lean MVP)

A local web app that wraps the proven Phase 0 analysis core. Upload a photo of an
engage2win thinking map, add a little context, and get a **Red/Amber/Green**
methodology evaluation plus a structured description — in about a minute.

It is a thin Flask UI: **all vision work is delegated to `validate/run.py`**
(the local `claude` CLI backend). No API key, no database, no Node.

## Run it

```bash
pip install -r app/requirements.txt        # Flask + jsonschema
# also needs the Phase 0 deps:
pip install -r validate/requirements.txt   # anthropic, jsonschema
python app/server.py                        # -> http://127.0.0.1:5000
```

You must have the `claude` CLI installed and on your PATH (same prerequisite as the
Phase 0 harness). The app shells out to it to read the map — no `ANTHROPIC_API_KEY`
is required.

## How it works

1. `GET /` — branded upload form (photo + participant/role/area/topic/language).
2. `POST /analyze` — saves the upload, starts a **background job**, returns a `job_id`.
3. `GET /status/<job_id>` — JSON the page polls for **live progress**:
   *Preparing → Reading & scoring → Writing the description → Done.*
4. `GET /result/<job_id>` — the result page:
   - the **photo side-by-side** with the report (sticky),
   - **tabs** (Evaluation / Description) to keep scrolling down,
   - the **RAG ball** + dimension badges — click any to change the rating,
   - all text is **editable** (click to fix) to support the *edit-not-redo* workflow,
   - a **copy** icon on the description and a **Copy evaluation** button for export.

Edits and rating changes are client-side only (there is no persistence by design in
the MVP) — make your corrections, then copy/print.

## Tests

```bash
python -m pytest app/tests/ -q     # CLI calls are mocked; no model calls
```

## Brand

Colours, fonts and logo come from the e2open brand
(`pptx-generator/brands/e2open`). Accent **#6E2AA8**, headers **#2B1146**.
Graphik is the brand font; the app falls back to a system sans where it isn't installed.

## Not in this MVP (future / production path)

No auth, no saved history, no Vercel deploy. The deployable production path
(Next.js + Supabase + Anthropic API key on Vercel) is a later phase — the
`claude`-CLI backend used here can't run on serverless.
