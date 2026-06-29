#!/usr/bin/env python3
"""
Validation harness for Engage2Win.

What it does
------------
1. Asks the user which language to use for output.
2. Reads every map photo in ../samples/.
3. For each photo, makes TWO calls to the vision model:
   a. Evaluation  — JSON matching schema.json (scores, verdict, etc.)
   b. Description — structured Markdown describing what is on the map
4. Saves output/<name>.json and output/<name>.description.md for each map.
5. Builds review.html so you can eyeball each map next to its AI evaluation
   and judge the "edit-not-redo" rate.

Usage
-----
    pip install -r requirements.txt
    python run.py                     # dry-run by default; uses stubs, no API needed
    python run.py --live              # real run via Anthropic SDK (needs ANTHROPIC_API_KEY)
    python run.py --claude-cli        # real run via local `claude` CLI (no API key needed)
    python run.py --limit 10          # process only the first 10 maps
    python run.py --rebuild           # rebuild review.html from saved outputs, no API calls
    python run.py --model claude-sonnet-4-6
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SAMPLES_DIR = ROOT / "samples"
OUTPUT_DIR = HERE / "output"
SCHEMA_PATH = HERE / "schema.json"
PROMPT_PATH = HERE / "prompt.md"
DESCRIBE_PROMPT_PATH = HERE / "describe_prompt.md"
REVIEW_PATH = HERE / "review.html"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif",
}
DEFAULT_MODEL = os.environ.get("MTT_MODEL", "claude-sonnet-4-6")
LANGUAGES = {"1": "es", "2": "ca", "3": "en"}
LANGUAGE_LABELS = {"es": "Spanish", "ca": "Catalan", "en": "English"}


# ---------------------------------------------------------------- env + helpers
def load_env():
    env_path = ROOT / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ask_language():
    print("Output language for this run:")
    print("  1. Spanish (es)")
    print("  2. Catalan (ca)")
    print("  3. English (en)")
    while True:
        choice = input("Select [1-3, default 3]: ").strip() or "3"
        if choice in LANGUAGES:
            lang = LANGUAGES[choice]
            print(f"  → {LANGUAGE_LABELS[lang]}\n")
            return lang
        print("  Please enter 1, 2, or 3.")


def load_context(image_path):
    """Optional sidecar JSON next to the image, e.g. map1.jpg -> map1.json."""
    sidecar = image_path.with_suffix(".json")
    ctx = {"name": "", "role": "", "area": "", "topic": "", "language": "en"}
    if sidecar.exists():
        try:
            ctx.update(json.loads(sidecar.read_text()))
        except json.JSONDecodeError:
            print(f"  ! {sidecar.name} is not valid JSON; ignoring it.")
    return ctx


def fill_prompt(template, ctx):
    out = template
    for key in ("name", "role", "area", "topic", "language"):
        out = out.replace("{{" + key + "}}", str(ctx.get(key) or "—"))
    return out


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")
    return json.loads(text[start:end + 1])


# ---------------------------------------------------------------- model calls
def _anthropic_client():
    try:
        import anthropic
        return anthropic.Anthropic()
    except ImportError:
        sys.exit("The 'anthropic' package is missing. Run: pip install -r requirements.txt")


def call_model(model, prompt_text, image_b64, media_type):
    client = _anthropic_client()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt_text},
            ],
        }],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


def describe_map(model, describe_template, ctx, image_b64, media_type):
    client = _anthropic_client()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": fill_prompt(describe_template, ctx)},
            ],
        }],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


# ---------------------------------------------------------------- claude CLI backend
def call_model_cli(model, prompt_text, image_path):
    """Call the local `claude` CLI with an image file. No API key needed."""
    result = subprocess.run(
        ["claude", "-p", prompt_text, "--image", str(image_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def describe_map_cli(model, describe_template, ctx, image_path):
    """Call the local `claude` CLI for the description pass."""
    prompt_text = fill_prompt(describe_template, ctx)
    result = subprocess.run(
        ["claude", "-p", prompt_text, "--image", str(image_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------- stubs (dry-run)
def stub_result(ctx):
    return {
        "overall": 74,
        "verdict": {"band": "mid", "title": "Solid map, room to deepen",
                    "text": "Good coverage of the topic; push for more strategic connections."},
        "dimensions": [
            {"key": "detail",     "score": 80, "comment": "Many specific notes across the sheet."},
            {"key": "insight",    "score": 65, "comment": "Mostly facts; few strategic connections drawn."},
            {"key": "clarity",    "score": 82, "comment": "Clear structure, legible handwriting."},
            {"key": "innovation", "score": 60, "comment": "Conventional framing; little original angle."},
            {"key": "rigor",      "score": 78, "comment": "Claims are grounded; one area needs more support."},
        ],
        "strengths": ["Wide coverage of the topic", "Clear visual organisation"],
        "recommendations": ["Add arrows linking causes to effects", "Group the loose notes on the right"],
        "questions": ["What would happen if this assumption were wrong?",
                      "Which insight here is most actionable, and why?"],
        "confidence": "medium",
        "language": ctx.get("language", "en"),
        "notes_reconstructed": [{"text": "(dry-run stub note)", "color": "yellow", "cluster": "A"}],
    }


def stub_description(ctx):
    topic = ctx.get("topic") or "the topic"
    return f"""## Map overview
Dry-run stub. In a real run, this would describe the engage2win map about "{topic}".

## Visual structure
[No image analysed in dry-run mode.]

## Content by zone / cluster
### Zone A
- Note 1
- Note 2

## Key ideas and connections
- Key idea 1 → Key idea 2

## Summary
This is a placeholder. Run without --dry-run to get a real description.
"""


# ---------------------------------------------------------------- normalise
def normalise(data):
    if isinstance(data.get("overall"), dict):
        nested = data["overall"]
        data["overall"] = nested.get("score", nested.get("overall", 0))
        if "verdict" not in data and "verdict" in nested:
            data["verdict"] = nested["verdict"]

    if "scores" in data and "dimensions" not in data:
        data["dimensions"] = data.pop("scores")
    for dim in data.get("dimensions", []):
        if "scores" in dim and "score" not in dim:
            dim["score"] = dim.pop("scores")

    conf = data.get("confidence")
    if isinstance(conf, (int, float)):
        data["confidence"] = "high" if conf >= 0.75 else ("medium" if conf >= 0.5 else "low")

    notes = data.get("notes_reconstructed", [])
    if notes and isinstance(notes[0], str):
        data["notes_reconstructed"] = [{"text": n} for n in notes]

    if isinstance(data.get("overall"), float):
        data["overall"] = int(data["overall"])
    for dim in data.get("dimensions", []):
        if isinstance(dim.get("score"), float):
            dim["score"] = int(dim["score"])

    return data


# ---------------------------------------------------------------- review page
def build_review(results):
    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    cards = []
    for r in results:
        ev, img_rel, status = r["eval"], r["image_rel"], r["status"]
        desc_html = ""
        if r.get("description"):
            desc_html = f'<pre class="desc">{esc(r["description"])}</pre>'

        if ev is None:
            eval_body = f'<p class="err">Failed: {esc(r.get("error",""))}</p>'
        else:
            dims = "".join(
                f'<div class="dim"><span>{esc(d["key"])}</span>'
                f'<div class="bar"><i style="width:{int(d["score"])}%"></i></div>'
                f'<b>{int(d["score"])}</b></div>' for d in ev.get("dimensions", [])
            )
            lst = lambda items: "".join(f"<li>{esc(x)}</li>" for x in items)
            band = ev.get("verdict", {}).get("band", "mid")
            eval_body = f"""
              <div class="verdict {band}">
                <div class="score">{int(ev.get('overall',0))}</div>
                <div><h3>{esc(ev.get('verdict',{}).get('title',''))}</h3>
                     <p>{esc(ev.get('verdict',{}).get('text',''))}</p>
                     <span class="chips">confidence: {esc(ev.get('confidence','—'))} ·
                       lang: {esc(ev.get('language','—'))}</span></div>
              </div>
              <div class="dims">{dims}</div>
              <div class="cols">
                <div><h4>Strengths</h4><ul>{lst(ev.get('strengths',[]))}</ul></div>
                <div><h4>Recommendations</h4><ul>{lst(ev.get('recommendations',[]))}</ul></div>
                <div><h4>Questions</h4><ul>{lst(ev.get('questions',[]))}</ul></div>
              </div>"""

        uid = esc(r["name"]).replace(" ", "_")
        tabs = ""
        if desc_html:
            tabs = f"""
              <div class="tabs">
                <button class="tab active" onclick="showTab('{uid}','eval',this)">Evaluation</button>
                <button class="tab" onclick="showTab('{uid}','desc',this)">Description</button>
              </div>"""

        cards.append(f"""
          <section class="card">
            <div class="photo"><img src="{esc(img_rel)}" alt="map"/>
              <div class="name">{esc(r['name'])} <span class="{status}">{status}</span></div></div>
            <div class="report">
              {tabs}
              <div id="{uid}_eval" class="tab-panel">
                {eval_body}
                <div class="judge">Edit-not-redo? &nbsp;
                  <label><input type="radio" name="j_{uid}"> faster to fix ✅</label>
                  <label><input type="radio" name="j_{uid}"> faster to redo ❌</label>
                </div>
              </div>
              {"<div id='" + uid + "_desc' class='tab-panel' style='display:none'>" + desc_html + "</div>" if desc_html else ""}
            </div>
          </section>""")

    ok = sum(1 for r in results if r["eval"] is not None)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Engage2Win · Phase 0 review</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#f4f5fb;color:#15163b}}
 header{{background:#15163b;color:#fff;padding:18px 24px}}
 header h1{{margin:0;font-size:18px}} header p{{margin:4px 0 0;color:#c9ccec;font-size:13px}}
 .wrap{{max-width:1100px;margin:20px auto;padding:0 16px;display:grid;gap:18px}}
 .card{{background:#fff;border-radius:14px;box-shadow:0 6px 20px rgba(20,22,59,.08);overflow:hidden;
        display:grid;grid-template-columns:minmax(260px,38%) 1fr}}
 @media(max-width:760px){{.card{{grid-template-columns:1fr}}}}
 .photo{{background:#0e0f2b;position:relative}} .photo img{{width:100%;height:100%;object-fit:contain;display:block}}
 .photo .name{{position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.55);color:#fff;
              padding:6px 10px;font-size:13px;display:flex;justify-content:space-between}}
 .ok{{color:#7CF0A0}} .fail{{color:#ff9a9a}}
 .report{{padding:16px 18px;overflow:auto}}
 .tabs{{display:flex;gap:6px;margin-bottom:12px;border-bottom:2px solid #eceefb;padding-bottom:6px}}
 .tab{{background:none;border:none;padding:5px 14px;border-radius:6px 6px 0 0;cursor:pointer;
       font-size:13px;color:#666;font-weight:500}}
 .tab.active{{background:#4F46E5;color:#fff}}
 .verdict{{display:flex;gap:14px;align-items:center;margin-bottom:12px}}
 .verdict .score{{width:58px;height:58px;border-radius:50%;display:grid;place-items:center;
                 font-weight:800;font-size:20px;color:#fff;flex:none}}
 .verdict.high .score{{background:#2e9e4f}} .verdict.mid .score{{background:#e0a200}} .verdict.low .score{{background:#d64545}}
 .verdict h3{{margin:0;font-size:15px}} .verdict p{{margin:2px 0 0;color:#555;font-size:13px}}
 .chips{{font-size:11px;color:#888}}
 .dims{{display:grid;gap:6px;margin:10px 0 14px}}
 .dim{{display:grid;grid-template-columns:90px 1fr 34px;align-items:center;gap:8px;font-size:12px}}
 .bar{{background:#eceefb;border-radius:6px;height:8px;overflow:hidden}} .bar i{{display:block;height:100%;background:#4F46E5}}
 .cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
 @media(max-width:680px){{.cols{{grid-template-columns:1fr}}}}
 .cols h4{{margin:0 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#4F46E5}}
 .cols ul{{margin:0;padding-left:16px;font-size:13px;color:#333}}
 .judge{{margin-top:14px;padding-top:10px;border-top:1px solid #eee;font-size:13px}}
 .judge label{{margin-right:14px;cursor:pointer}}
 .desc{{background:#f8f9ff;border:1px solid #e0e2f0;border-radius:8px;padding:14px;
        font-size:13px;line-height:1.6;white-space:pre-wrap;font-family:inherit;overflow:auto}}
 .err{{color:#d64545}}
</style>
<script>
function showTab(uid, tab, btn) {{
  document.getElementById(uid+'_eval').style.display = tab==='eval' ? '' : 'none';
  var d = document.getElementById(uid+'_desc');
  if (d) d.style.display = tab==='desc' ? '' : 'none';
  btn.closest('.tabs').querySelectorAll('.tab').forEach(function(b){{b.classList.remove('active')}});
  btn.classList.add('active');
}}
</script>
</head><body>
<header><h1>Engage2Win — Phase 0 review</h1>
<p>{ok} of {len(results)} maps evaluated. For each, decide: is correcting the AI faster than redoing it?
Tally the ✅ to get your edit-not-redo rate (target &gt; 80%).</p></header>
<div class="wrap">{''.join(cards)}</div></body></html>"""
    REVIEW_PATH.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True, help="No API calls; use stub results (default).")
    ap.add_argument("--live", action="store_true", help="Make real API calls via Anthropic SDK (requires ANTHROPIC_API_KEY).")
    ap.add_argument("--claude-cli", action="store_true", dest="claude_cli", help="Make real calls via local `claude` CLI (no API key needed).")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="Process only the first N maps (0 = all).")
    ap.add_argument("--rebuild", action="store_true", help="Rebuild review.html from saved outputs, no API calls.")
    args = ap.parse_args()
    if args.live or args.claude_cli:
        args.dry_run = False

    load_env()
    OUTPUT_DIR.mkdir(exist_ok=True)

    if args.rebuild:
        results = []
        for json_file in sorted(OUTPUT_DIR.glob("*.json")):
            if json_file.stem.endswith(".INVALID"):
                continue
            stem = json_file.stem
            img = next((SAMPLES_DIR / f"{stem}{ext}" for ext in IMAGE_EXTS
                        if (SAMPLES_DIR / f"{stem}{ext}").exists()), None)
            if img is None:
                continue
            ev = json.loads(json_file.read_text(encoding="utf-8"))
            desc_file = OUTPUT_DIR / f"{stem}.description.md"
            desc = desc_file.read_text(encoding="utf-8") if desc_file.exists() else None
            results.append({"name": stem, "image_rel": os.path.relpath(img, HERE),
                            "status": "ok", "eval": ev, "description": desc, "error": ""})
        build_review(results)
        print(f"Rebuilt review.html from {len(results)} saved outputs. Open: {REVIEW_PATH}")
        return

    try:
        from jsonschema import validate as js_validate, ValidationError
    except ImportError:
        sys.exit("The 'jsonschema' package is missing. Run: pip install -r requirements.txt")

    schema = json.loads(SCHEMA_PATH.read_text())
    prompt_template = PROMPT_PATH.read_text()
    describe_template = DESCRIBE_PROMPT_PATH.read_text() if DESCRIBE_PROMPT_PATH.exists() else None

    images = sorted(p for p in SAMPLES_DIR.iterdir()
                    if p.is_file() and p.suffix.lower() in IMAGE_EXTS) if SAMPLES_DIR.exists() else []
    if not images:
        print(f"No images found in {SAMPLES_DIR}. Add map photos (.jpg/.png) and re-run.")
        return

    if args.limit > 0:
        images = images[:args.limit]

    if args.live and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set. Put it in ../.env.local, or use --claude-cli instead.")

    language = ask_language() if not args.dry_run else "en"

    mode_label = " [DRY RUN]" if args.dry_run else (" [claude CLI]" if args.claude_cli else " [live SDK]")
    print(f"Evaluating {len(images)} map(s) with model '{args.model}'{mode_label}\n")

    results = []
    for img in images:
        ctx = load_context(img)
        ctx["language"] = language
        print(f"• {img.name}")

        rec = {"name": img.stem, "image_rel": os.path.relpath(img, HERE),
               "status": "ok", "eval": None, "description": None, "error": ""}

        try:
            if args.dry_run:
                data = stub_result(ctx)
                b64 = None
            elif args.claude_cli:
                raw = call_model_cli(args.model, fill_prompt(prompt_template, ctx), img)
                data = extract_json(raw)
                b64 = None
            else:
                b64 = base64.b64encode(img.read_bytes()).decode()
                raw = call_model(args.model, fill_prompt(prompt_template, ctx),
                                 b64, MEDIA_TYPES[img.suffix.lower()])
                data = extract_json(raw)

            data = normalise(data)
            js_validate(instance=data, schema=schema)
            (OUTPUT_DIR / f"{img.stem}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            rec["eval"] = data
            print(f"  evaluation  ✓")

        except ValidationError as e:
            rec["status"], rec["error"] = "fail", f"schema: {e.message}"
            try:
                (OUTPUT_DIR / f"{img.stem}.INVALID.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            print(f"  evaluation  ✗  {e.message}")

        except Exception as e:
            rec["status"], rec["error"] = "fail", str(e)
            print(f"  evaluation  ✗  {e}")

        if rec["eval"] is not None and describe_template:
            try:
                print(f"  description ...", end=" ", flush=True)
                if args.dry_run:
                    desc_md = stub_description(ctx)
                elif args.claude_cli:
                    desc_md = describe_map_cli(args.model, describe_template, ctx, img)
                else:
                    desc_md = describe_map(args.model, describe_template, ctx,
                                           b64, MEDIA_TYPES[img.suffix.lower()])
                (OUTPUT_DIR / f"{img.stem}.description.md").write_text(desc_md, encoding="utf-8")
                rec["description"] = desc_md
                print("✓")
            except Exception as e:
                print(f"✗  {e}")

        results.append(rec)

    build_review(results)
    ok = sum(1 for r in results if r["eval"] is not None)
    print(f"\nDone. {ok}/{len(results)} valid. Open: {REVIEW_PATH}")
    print("Each map has an Evaluation tab and a Description tab in the review page.")


if __name__ == "__main__":
    main()
