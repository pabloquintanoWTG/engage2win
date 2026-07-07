"""Customers + Sessions + Participants (Phase 2).

CRUD over the session-planning entities, all behind login and scoped by ownership
(facilitators see only their own; admins see all). Cross-user access returns 404 so
we don't leak the existence of other users' data.
"""
from datetime import date

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort)
from flask_login import login_required, current_user

from models import (db, Customer, Session, Participant, owned,
                    LANGUAGES, SESSION_STATUSES)

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
