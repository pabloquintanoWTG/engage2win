# Engage2Win — AI Map Evaluator

AI-powered evaluation of engage2win thinking maps for e2open / WiseTech Global.

A participant uploads a photo of a thinking map created during an engage2win session
and gets a structured evaluation: overall score, five dimension scores, strengths,
recommendations, and follow-up questions — plus a full structured description of the
map's content.

## Quick start

1. Copy `.env.example` to `.env.local` and paste your Anthropic API key.
2. Drop map photos (`.jpg`/`.png`) into `/samples`.
3. Double-click `run-validation.bat` (or run `python validate/run.py`).
4. Open `validate/review.html` to see the results.

## Project structure

```
engage2win/
├── CLAUDE.md              ← project context for Claude Code
├── README.md              ← this file
├── .env.example           ← secrets template (copy to .env.local)
├── run-validation.bat     ← double-click to run
├── validate/
│   ├── run.py             ← main harness
│   ├── prompt.md          ← evaluation prompt (tune this)
│   ├── describe_prompt.md ← description prompt
│   ├── schema.json        ← output contract
│   ├── requirements.txt
│   └── output/            ← generated (gitignored)
└── samples/               ← drop map photos here (gitignored)
```

## Commands

```bash
python validate/run.py              # run all maps
python validate/run.py --limit 10   # run first 10 only
python validate/run.py --rebuild    # rebuild review.html from saved outputs
python validate/run.py --dry-run    # test pipeline without API calls
```
