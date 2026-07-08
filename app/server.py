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

import os
import sys
import threading
import uuid
from pathlib import Path

from flask import (Flask, render_template, request, jsonify, send_from_directory,
                   abort, url_for, redirect)
from werkzeug.utils import secure_filename

# --- make the proven Phase 0 core importable -------------------------------
APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
VALIDATE_DIR = ROOT / "validate"
sys.path.insert(0, str(VALIDATE_DIR))
sys.path.insert(0, str(APP_DIR))
import run  # noqa: E402  (validate/run.py — analysis core, reused as-is)

from jsonschema import validate as js_validate, ValidationError  # noqa: E402
from flask_login import LoginManager, login_required, current_user  # noqa: E402
from models import db, User, Customer, Session, owned  # noqa: E402
from auth import auth_bp  # noqa: E402
from workspace import workspace_bp  # noqa: E402
from agenda import agenda_bp  # noqa: E402

UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 20 * 1024 * 1024  # 20 MB
LANGUAGES = {"es", "ca", "en"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES

run.load_env()

# --- auth + database -------------------------------------------------------
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "dev-insecure-change-me"
if app.config["SECRET_KEY"] == "dev-insecure-change-me":
    print("WARNING: SECRET_KEY not set — using an insecure dev key. Set SECRET_KEY in .env.local.")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    os.environ.get("DATABASE_URL") or f"sqlite:///{APP_DIR / 'engage2win.db'}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"

# API routes answer XHR with JSON; pages redirect to the login screen.
_API_PREFIXES = ("/analyze", "/status")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def _unauthorized():
    if request.path.startswith(_API_PREFIXES):
        return jsonify(error="Please sign in to continue."), 401
    return redirect(url_for("auth.login", next=request.path))


app.register_blueprint(auth_bp)
app.register_blueprint(workspace_bp)
app.register_blueprint(agenda_bp)

with app.app_context():
    db.create_all()
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
@app.errorhandler(413)
def too_large(_e):
    mb = MAX_BYTES // (1024 * 1024)
    return jsonify(error=f"That photo is too large (limit {mb} MB). Try a smaller image."), 413


@app.route("/")
@login_required
def index():
    # Workspace dashboard: the user's customers (admins see all) + quick actions.
    customers = owned(Customer, current_user).order_by(Customer.name).all()
    session_count = owned(Session, current_user).count()
    return render_template("home.html", customers=customers, session_count=session_count)


@app.route("/analyze/new")
@login_required
def analyze_new():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
@login_required
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
        _JOBS[job_id] = {"state": "running", "step": "prepare", "owner_id": current_user.id,
                         "image": image_path.name, "ctx": ctx, "result": None, "error": None}

    threading.Thread(target=run_job, args=(job_id, image_path, ctx, model), daemon=True).start()
    return jsonify(job_id=job_id), 202


def _owned_job(job_id):
    """Return the job only if it belongs to the current user, else None."""
    with _LOCK:
        job = _JOBS.get(job_id)
    if job is None or job.get("owner_id") != current_user.id:
        return None
    return job


@app.route("/status/<job_id>")
@login_required
def status(job_id):
    job = _owned_job(job_id)
    if job is None:
        return jsonify(error="Unknown job."), 404
    payload = {"state": job["state"], "step": job["step"],
               "label": STEP_LABELS.get(job["step"], ""), "error": job["error"]}
    if payload["state"] == "done":
        payload["result_url"] = url_for("result", job_id=job_id)
    return jsonify(payload)


@app.route("/result/<job_id>")
@login_required
def result(job_id):
    job = _owned_job(job_id)
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
@login_required
def uploaded_file(filename):
    # Only serve an upload that belongs to one of the current user's jobs.
    with _LOCK:
        owned = any(j.get("image") == filename and j.get("owner_id") == current_user.id
                    for j in _JOBS.values())
    if not owned:
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    print("Engage2Win MVP  ->  http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
