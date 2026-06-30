#!/usr/bin/env python3
"""
Engage2Win — Phase 1 Lean MVP web app.

A thin Flask UI over the PROVEN Phase 0 analysis core. All vision work is
delegated to validate/run.py (the local `claude` CLI backend), so this file
contains no model logic of its own — it only handles uploads, runs the
analysis in a background thread, exposes progress for live polling, and
renders the branded result page.

Run:
    pip install -r app/requirements.txt
    python app/server.py            # http://127.0.0.1:5000
"""

import sys
import threading
import uuid
from pathlib import Path

from flask import (Flask, render_template, request, jsonify, send_from_directory,
                   abort, url_for)
from werkzeug.utils import secure_filename

# --- make the proven Phase 0 core importable -------------------------------
APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
VALIDATE_DIR = ROOT / "validate"
sys.path.insert(0, str(VALIDATE_DIR))
import run  # noqa: E402  (validate/run.py — analysis core, reused as-is)

from jsonschema import validate as js_validate, ValidationError  # noqa: E402

UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 20 * 1024 * 1024  # 20 MB
LANGUAGES = {"es", "ca", "en"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES

run.load_env()
_SCHEMA = None
_PROMPT = None
_DESCRIBE = None


def _resources():
    """Lazy-load prompt/schema once (also lets tests monkeypatch run.* first)."""
    global _SCHEMA, _PROMPT, _DESCRIBE
    if _SCHEMA is None:
        _SCHEMA = run.json.loads(run.SCHEMA_PATH.read_text(encoding="utf-8"))
        _PROMPT = run.PROMPT_PATH.read_text(encoding="utf-8")
        _DESCRIBE = (run.DESCRIBE_PROMPT_PATH.read_text(encoding="utf-8")
                     if run.DESCRIBE_PROMPT_PATH.exists() else None)
    return _SCHEMA, _PROMPT, _DESCRIBE


# --- in-memory job store (single-user local tool; no DB by design) ---------
_JOBS = {}
_LOCK = threading.Lock()

STEPS = ["prepare", "evaluate", "describe", "done"]
STEP_LABELS = {
    "prepare":  "Preparing the map",
    "evaluate": "Reading & scoring the map",
    "describe": "Writing the description",
    "done":     "Done",
}


def _set(job_id, **kw):
    with _LOCK:
        _JOBS[job_id].update(kw)


def run_job(job_id, image_path, ctx, model):
    """Worker: run the two proven CLI passes and store the validated result.

    Kept as a plain callable (not a closure) so tests can invoke it directly
    with the claude CLI mocked.
    """
    schema, prompt_tpl, describe_tpl = _resources()
    try:
        _set(job_id, step="evaluate")
        raw = run.call_model_cli(model, run.fill_prompt(prompt_tpl, ctx), image_path)
        data = run.normalise(run.extract_json(raw))
        js_validate(instance=data, schema=schema)

        description = None
        if describe_tpl:
            _set(job_id, step="describe")
            description = run.describe_map_cli(model, describe_tpl, ctx, image_path)

        _set(job_id, step="done", state="done", result={"eval": data, "description": description})
    except ValidationError as e:
        _set(job_id, state="error", error=f"The evaluation didn't match the schema: {e.message}")
    except Exception as e:  # CLI missing, non-JSON output, etc.
        _set(job_id, state="error", error=str(e))


# --- routes ----------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    file = request.files.get("image")
    if file is None or not file.filename:
        return jsonify(error="Please choose a map photo to analyze."), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return jsonify(error=f"Unsupported file type '{ext}'. Use JPG, PNG or WEBP."), 400

    language = request.form.get("language", "en")
    if language not in LANGUAGES:
        language = "en"

    job_id = uuid.uuid4().hex
    safe = secure_filename(file.filename) or "map"
    image_path = UPLOAD_DIR / f"{job_id}__{safe}"
    file.save(str(image_path))

    ctx = {
        "name": request.form.get("name", "").strip(),
        "role": request.form.get("role", "").strip(),
        "area": request.form.get("area", "").strip(),
        "topic": request.form.get("topic", "").strip(),
        "language": language,
    }
    model = request.form.get("model") or run.DEFAULT_MODEL

    with _LOCK:
        _JOBS[job_id] = {"state": "running", "step": "prepare",
                         "image": image_path.name, "ctx": ctx, "result": None, "error": None}

    threading.Thread(target=run_job, args=(job_id, image_path, ctx, model), daemon=True).start()
    return jsonify(job_id=job_id), 202


@app.route("/status/<job_id>")
def status(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return jsonify(error="Unknown job."), 404
        payload = {"state": job["state"], "step": job["step"],
                   "label": STEP_LABELS.get(job["step"], ""), "error": job["error"]}
    if payload["state"] == "done":
        payload["result_url"] = url_for("result", job_id=job_id)
    return jsonify(payload)


@app.route("/result/<job_id>")
def result(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
    if job is None or job.get("state") != "done":
        abort(404)
    ev = job["result"]["eval"]
    band = run.rag(ev.get("overall", 0))
    dims = [{**d, "band": run.rag(d.get("score", 0)),
             "label": run.RAG_LABEL[run.rag(d.get("score", 0))]} for d in ev.get("dimensions", [])]
    return render_template(
        "result.html",
        ctx=job["ctx"],
        image_url=url_for("uploaded_file", filename=job["image"]),
        ev=ev, band=band, band_label=run.RAG_LABEL[band], dims=dims,
        description=job["result"]["description"] or "",
        rag_labels=run.RAG_LABEL,
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    print("Engage2Win MVP  ->  http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
