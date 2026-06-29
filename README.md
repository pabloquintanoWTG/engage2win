# Engage2Win — AI Map Evaluator

AI-powered evaluation of engage2win thinking maps for e2open / WiseTech Global.

A participant uploads a photo of a thinking map created during an engage2win session
and gets a structured evaluation: overall score, five dimension scores, strengths,
recommendations, and follow-up questions — plus a full structured description of the
map's content.

## Quick start

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
├── validate/
│   ├── run.py             ← main harness
│   ├── prompt.md          ← evaluation prompt (tune this)
│   ├── describe_prompt.md ← description prompt
│   ├── schema.json        ← output contract
│   ├── requirements.txt
│   ├── tests/             ← unit tests (pytest)
│   └── output/            ← generated (gitignored)
└── samples/               ← drop map photos here (gitignored)
```

## Running tests

```bash
pip install pytest
python -m pytest validate/tests/ -v
```
