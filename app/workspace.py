"""Customers + Sessions + Participants (Phase 2) + Maps (Phase 4).

CRUD over the session-planning entities, all behind login and scoped by ownership
(facilitators see only their own; admins see all). Cross-user access returns 404 so
we don't leak the existence of other users' data.
"""
import json
import os
import sys
import threading
import uuid
from datetime import date
from pathlib import Path

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, current_app, send_from_directory, jsonify)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import (db, Customer, Session, Participant, MapAnalysis, owned, utcnow,
                    LANGUAGES, SESSION_STATUSES, MAP_TYPES, MAP_MECHANICS)
from analysis_status import (status_payload, explain_error, interrupted_error,
                             NoBackendError)

# --- Phase 4: set up validate/run.py import path
ROOT = Path(__file__).resolve().parent.parent
VALIDATE_DIR = ROOT / "validate"
if str(VALIDATE_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATE_DIR))

workspace_bp = Blueprint("workspace", __name__)


def _get_customer_or_404(customer_id):
    c = owned(Customer, current_user).filter(Customer.id == customer_id).first()
    if c is None:
        abort(404)
    return c


def _get_session_or_404(session_id):
    s = owned(Session, current_user).filter(Session.id == session_id).first()
    if s is None:
        abort(404)
    return s


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# ---------------------------------------------------------------- customers
@workspace_bp.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Customer name is required.", "error")
            return render_template("customers.html",
                                   customers=_customer_list(), name_error=True), 400
        c = Customer(owner_user_id=current_user.id, name=name,
                     industry=request.form.get("industry", "").strip(),
                     notes=request.form.get("notes", "").strip())
        db.session.add(c)
        db.session.commit()
        flash("Customer created.", "ok")
        return redirect(url_for("workspace.customer_detail", customer_id=c.id))
    return render_template("customers.html", customers=_customer_list())


def _customer_list():
    return owned(Customer, current_user).order_by(Customer.name).all()


@workspace_bp.route("/customers/<int:customer_id>")
@login_required
def customer_detail(customer_id):
    c = _get_customer_or_404(customer_id)
    return render_template("customer_detail.html", customer=c, languages=LANGUAGES)


@workspace_bp.route("/customers/<int:customer_id>/edit", methods=["POST"])
@login_required
def edit_customer(customer_id):
    c = _get_customer_or_404(customer_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Customer name is required.", "error")
        return redirect(url_for("workspace.customer_detail", customer_id=c.id))
    c.name = name
    c.industry = request.form.get("industry", "").strip()
    c.notes = request.form.get("notes", "").strip()
    db.session.commit()
    flash("Customer updated.", "ok")
    return redirect(url_for("workspace.customer_detail", customer_id=c.id))


@workspace_bp.route("/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
def delete_customer(customer_id):
    c = _get_customer_or_404(customer_id)
    # Delete all map image files from all sessions under this customer
    for session in c.sessions:
        for m in session.map_analyses:
            if os.path.exists(m.image_path):
                try:
                    os.remove(m.image_path)
                except Exception:
                    pass
    db.session.delete(c)  # CASCADE deletes sessions, participants, maps, agenda items
    db.session.commit()
    flash("Customer deleted (including all sessions and maps).", "ok")
    return redirect(url_for("workspace.customers"))


# ---------------------------------------------------------------- sessions
@workspace_bp.route("/customers/<int:customer_id>/sessions", methods=["POST"])
@login_required
def create_session(customer_id):
    c = _get_customer_or_404(customer_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash("Session title is required.", "error")
        return redirect(url_for("workspace.customer_detail", customer_id=c.id))
    language = request.form.get("language", "en")
    if language not in LANGUAGES:
        language = "en"
    s = Session(customer_id=c.id, owner_user_id=current_user.id, title=title,
                objectives=request.form.get("objectives", "").strip(),
                language=language,
                scheduled_date=_parse_date(request.form.get("scheduled_date")))
    db.session.add(s)
    db.session.commit()
    flash("Session created.", "ok")
    return redirect(url_for("workspace.session_workspace", session_id=s.id))


@workspace_bp.route("/sessions/<int:session_id>")
@login_required
def session_workspace(session_id):
    s = _get_session_or_404(session_id)
    return render_template("session.html", session=s,
                           languages=LANGUAGES, statuses=SESSION_STATUSES)


@workspace_bp.route("/sessions/<int:session_id>/edit", methods=["POST"])
@login_required
def edit_session(session_id):
    s = _get_session_or_404(session_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash("Session title is required.", "error")
        return redirect(url_for("workspace.session_workspace", session_id=s.id))
    s.title = title
    s.objectives = request.form.get("objectives", "").strip()
    status = request.form.get("status", s.status)
    if status in SESSION_STATUSES:
        s.status = status
    language = request.form.get("language", s.language)
    if language in LANGUAGES:
        s.language = language
    s.scheduled_date = _parse_date(request.form.get("scheduled_date"))
    db.session.commit()
    flash("Session updated.", "ok")
    return redirect(url_for("workspace.session_workspace", session_id=s.id))


@workspace_bp.route("/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
def delete_session(session_id):
    s = _get_session_or_404(session_id)
    cid = s.customer_id
    # Delete all map image files from this session
    for m in s.map_analyses:
        if os.path.exists(m.image_path):
            try:
                os.remove(m.image_path)
            except Exception:
                pass
    db.session.delete(s)  # CASCADE deletes participants, maps, agenda items
    db.session.commit()
    flash("Session deleted (including all participants, maps, and agenda items).", "ok")
    return redirect(url_for("workspace.customer_detail", customer_id=cid))


# ---------------------------------------------------------------- participants
@workspace_bp.route("/sessions/<int:session_id>/participants", methods=["POST"])
@login_required
def add_participant(session_id):
    s = _get_session_or_404(session_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Participant name is required.", "error")
        return redirect(url_for("workspace.session_workspace", session_id=s.id))
    p = Participant(session_id=s.id, name=name,
                    role_dept=request.form.get("role_dept", "").strip(),
                    email=(request.form.get("email", "").strip() or None))
    db.session.add(p)
    db.session.commit()
    flash("Participant added.", "ok")
    return redirect(url_for("workspace.session_workspace", session_id=s.id))


@workspace_bp.route("/sessions/<int:session_id>/participants/<int:pid>/delete", methods=["POST"])
@login_required
def remove_participant(session_id, pid):
    s = _get_session_or_404(session_id)
    p = Participant.query.filter(Participant.id == pid,
                                 Participant.session_id == s.id).first()
    if p is not None:
        db.session.delete(p)
        db.session.commit()
        flash("Participant removed.", "ok")
    return redirect(url_for("workspace.session_workspace", session_id=s.id))


# ---------------------------------------------------------------- Phase 4: map analysis
def _get_map_or_404(map_id, session_id):
    m = MapAnalysis.query.filter(MapAnalysis.id == map_id,
                                 MapAnalysis.session_id == session_id).first()
    if m is None:
        abort(404)
    return m


@workspace_bp.route("/sessions/<int:session_id>/maps", methods=["GET"])
@login_required
def map_list(session_id):
    s = _get_session_or_404(session_id)
    maps = MapAnalysis.query.filter(MapAnalysis.session_id == s.id)\
                             .order_by(MapAnalysis.created_at.desc()).all()
    return render_template("map_list.html", session=s, maps=maps,
                          map_types=MAP_TYPES, mechanics=MAP_MECHANICS)


@workspace_bp.route("/sessions/<int:session_id>/maps/upload", methods=["POST"])
@login_required
def upload_map(session_id):
    s = _get_session_or_404(session_id)

    map_type = request.form.get("map_type", "").strip()
    if not map_type or map_type not in MAP_TYPES:
        flash("Invalid map type.", "error")
        return redirect(url_for("workspace.map_list", session_id=s.id))

    participant_name = request.form.get("participant_name", "").strip() or None
    role_context = request.form.get("role_context", "").strip() or None

    if "image" not in request.files:
        flash("No image uploaded.", "error")
        return redirect(url_for("workspace.map_list", session_id=s.id))

    file = request.files["image"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("workspace.map_list", session_id=s.id))

    UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
    UPLOAD_DIR.mkdir(exist_ok=True)
    ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_BYTES = 20 * 1024 * 1024

    if len(file.read()) > MAX_BYTES:
        file.seek(0)
        flash(f"File exceeds {MAX_BYTES // (1024*1024)}MB limit.", "error")
        return redirect(url_for("workspace.map_list", session_id=s.id))
    file.seek(0)

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        flash(f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTS)}", "error")
        return redirect(url_for("workspace.map_list", session_id=s.id))

    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    file_path = UPLOAD_DIR / filename
    file.save(file_path)

    m = MapAnalysis(
        session_id=s.id,
        map_type=map_type,
        image_path=str(file_path),
        eval_json="{}",
        band=None,  # Not evaluated yet
        status="pending",
        participant_name=participant_name,
        role_context=role_context,
    )
    db.session.add(m)
    db.session.commit()

    # The form says "Upload and analyze" — start straight away.
    _start_analysis(s, m)
    flash("Map uploaded — analysis started. Progress is shown below.", "ok")
    return redirect(url_for("workspace.map_detail", session_id=s.id, map_id=m.id))


@workspace_bp.route("/sessions/<int:session_id>/maps/<int:map_id>", methods=["GET"])
@login_required
def map_detail(session_id, map_id):
    s = _get_session_or_404(session_id)
    m = _get_map_or_404(map_id, session_id)
    _reconcile_orphan(m)

    mechanics = MAP_MECHANICS.get(m.map_type, {})
    eval_data = {}
    if m.eval_json and m.eval_json != "{}":
        try:
            eval_data = json.loads(m.eval_json)
        except (json.JSONDecodeError, TypeError):
            eval_data = {}  # Invalid JSON stored, show empty results

    return render_template("map_detail.html", session=s, map=m,
                          mechanics=mechanics, eval_data=eval_data,
                          status=_map_status_payload(m))


# Map ids with a live worker thread in this process. A row that says "running"
# but isn't here was orphaned by an app restart and is reported as interrupted.
_ACTIVE_ANALYSES = set()
_ACTIVE_LOCK = threading.Lock()


def run_map_analysis(app_obj, map_id, params):
    """Worker: run the Phase 0 core for one map, recording each step on the row.

    A plain function (not a closure) so tests can call it synchronously with the
    analysis core mocked. `params` holds plain values captured from the request
    (ORM instances are not thread-safe).
    """
    import run  # validate/run.py (path set up at import time above)

    step = "prepare"

    def set_step(new_step):
        nonlocal step
        step = new_step
        row = db.session.get(MapAnalysis, map_id)
        if row:
            row.step = new_step
            db.session.commit()

    with app_obj.app_context():
        try:
            backend = run.resolve_backend(None)
            if backend == "dry_run":
                raise NoBackendError("resolve_backend() found no claude CLI and no ANTHROPIC_API_KEY")
            eval_dict, desc_md = run.analyze_map(backend=backend, on_step=set_step, **params)
            row = db.session.get(MapAnalysis, map_id)
            if row:
                row.eval_json = json.dumps(eval_dict, ensure_ascii=False)
                row.description_md = desc_md or ""
                row.band = run.rag(eval_dict.get("overall", 0))
                row.status = "done"
                row.step = "done"
                row.error_json = None
                row.finished_at = utcnow()
                db.session.commit()
        except Exception as e:
            app_obj.logger.exception("Map analysis %s failed during '%s'", map_id, step)
            db.session.rollback()
            row = db.session.get(MapAnalysis, map_id)
            if row:
                row.status = "error"
                row.band = None  # Keep band clean on error
                row.error_json = json.dumps(explain_error(e, step), ensure_ascii=False)
                row.finished_at = utcnow()
                db.session.commit()
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_ANALYSES.discard(map_id)
            db.session.remove()


def _start_analysis(s, m):
    """Mark the map running and start the worker. Returns False if already running."""
    with _ACTIVE_LOCK:
        if m.id in _ACTIVE_ANALYSES:
            return False
        _ACTIVE_ANALYSES.add(m.id)

    m.status = "running"
    m.step = "prepare"
    m.error_json = None
    m.started_at = utcnow()
    m.finished_at = None
    db.session.commit()

    params = dict(image_path=m.image_path, map_type=m.map_type,
                  participant_name=m.participant_name, role_context=m.role_context,
                  session_topic=s.title, language=s.language)
    threading.Thread(target=run_map_analysis,
                     args=(current_app._get_current_object(), m.id, params),
                     daemon=True).start()
    return True


def _reconcile_orphan(m):
    """A row stuck at "running" with no live worker (app restarted) → error."""
    if m.status != "running":
        return
    with _ACTIVE_LOCK:
        alive = m.id in _ACTIVE_ANALYSES
    if not alive:
        m.status = "error"
        m.error_json = json.dumps(interrupted_error(m.step))
        m.finished_at = utcnow()
        db.session.commit()


@workspace_bp.route("/sessions/<int:session_id>/maps/<int:map_id>/analyze", methods=["POST"])
@login_required
def analyze_map_route(session_id, map_id):
    s = _get_session_or_404(session_id)
    m = _get_map_or_404(map_id, session_id)
    if _start_analysis(s, m):
        flash("Analysis started — progress is shown below.", "ok")
    else:
        flash("This map is already being analysed.", "error")
    return redirect(url_for("workspace.map_detail", session_id=s.id, map_id=m.id))


@workspace_bp.route("/api/sessions/<int:session_id>/maps/<int:map_id>/status")
@login_required
def map_status(session_id, map_id):
    _get_session_or_404(session_id)
    m = _get_map_or_404(map_id, session_id)
    _reconcile_orphan(m)
    return jsonify(_map_status_payload(m))


def _map_status_payload(m):
    import run
    error = m.get_error()
    if m.status == "error" and error is None:
        # Rows analysed before error_json existed kept a bare {"error": "..."} in eval_json.
        try:
            legacy = json.loads(m.eval_json or "{}").get("error")
        except (json.JSONDecodeError, TypeError, AttributeError):
            legacy = None
        error = {"title": "Analysis failed", "where": "Analysis",
                 "message": legacy or "The previous analysis failed.",
                 "fix": "Click Retry analysis."}
    return status_payload(m.status, m.step, m.started_at, m.finished_at,
                          error, timeout_s=run.CLI_TIMEOUT_S)


@workspace_bp.route("/sessions/<int:session_id>/maps/<int:map_id>/image")
@login_required
def map_image(session_id, map_id):
    s = _get_session_or_404(session_id)
    m = _get_map_or_404(map_id, session_id)
    if not os.path.exists(m.image_path):
        abort(404)
    return send_from_directory(os.path.dirname(m.image_path), os.path.basename(m.image_path))


@workspace_bp.route("/sessions/<int:session_id>/maps/<int:map_id>/delete", methods=["POST"])
@login_required
def delete_map(session_id, map_id):
    s = _get_session_or_404(session_id)
    m = _get_map_or_404(map_id, session_id)

    if os.path.exists(m.image_path):
        try:
            os.remove(m.image_path)
        except Exception:
            pass

    db.session.delete(m)
    db.session.commit()
    flash("Map deleted.", "ok")
    return redirect(url_for("workspace.map_list", session_id=s.id))
