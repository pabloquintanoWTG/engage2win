# Engage2Win — AI Map Evaluator

AI-powered evaluation of engage2win thinking maps for e2open / WiseTech Global.

A participant uploads a photo of a thinking map created during an engage2win session
and gets a structured evaluation: an overall **Red/Amber/Green** verdict, a RAG rating
across five dimensions, strengths, recommendations, and follow-up questions — plus a
full structured description of the map's content.

The project has two parts:
- **`validate/`** — the Phase 0 validation harness (batch-analyses a folder of maps and
  builds a review page). Used to prove the AI before building the app.
- **`app/`** — the Phase 1 **Lean MVP web app**: a local, e2open-branded Flask app to
  upload one map and get an editable RAG result. See [`app/README.md`](app/README.md).

## Run the app (Phase 1)

```bash
pip install -r app/requirements.txt -r validate/requirements.txt
python app/server.py            # -> http://127.0.0.1:5000
```

Requires the `claude` CLI on your PATH (no API key needed). Upload a map photo, add
context, and get a live-progress analysis → editable RAG evaluation + description.

## Validation harness — Quick start (Phase 0)

### Option A — Claude CLI (recommended, no API key needed)
1. Drop map photos (`.jpg`/`.png`) into `/samples`.
2. Run `python validate/run.py --claude-cli`
3. Open `validate/review.html` to see the results.

### Option B — Anthropic SDK (requires API key)
1. Copy `.env.example` to `.env.local` and paste your Anthropic API key.
2. Drop map photos into `/samples`.
3. Run `python validate/run.py --live` (or double-click `run-validation.bat`).
4. Open `validate/review.html` to see the results.

## Commands

```bash
python validate/run.py                    # dry-run (stubs, no API needed)
python validate/run.py --claude-cli       # real analysis via local claude CLI
python validate/run.py --live             # real analysis via Anthropic SDK
python validate/run.py --limit 10         # process first 10 maps only
python validate/run.py --rebuild          # rebuild review.html from saved outputs
```

## Project structure

```
engage2win/
├── CLAUDE.md              ← project context for Claude Code
├── README.md              ← this file
├── .env.example           ← secrets template (copy to .env.local for --live mode)
├── run-validation.bat     ← double-click shortcut
├── validate/              ← Phase 0 validation harness
│   ├── run.py             ← main harness (analysis core, reused by the app)
│   ├── prompt.md          ← evaluation prompt (tune this)
│   ├── describe_prompt.md ← description prompt
│   ├── schema.json        ← output contract (verdict.band ∈ green|amber|red)
│   ├── requirements.txt
│   ├── tests/             ← unit tests (pytest)
│   └── output/            ← generated (gitignored)
├── app/                   ← Phase 1 Lean MVP web app (Flask)
│   ├── server.py          ← routes + background job; imports validate/run.py
│   ├── templates/         ← upload form + result page (tabs, editable, copy)
│   ├── static/            ← e2open-branded CSS + logo
│   ├── tests/             ← app tests (pytest, claude CLI mocked)
│   └── uploads/           ← uploaded photos (gitignored)
└── samples/               ← drop map photos here (gitignored)
```

## Running tests

```bash
pip install pytest
python -m pytest validate/tests app/tests -v
```
