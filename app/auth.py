"""Authentication + invitations blueprint (Phase 1).

Account rules (see docs/prd/phase1-auth-spec.md):
- First-ever registration creates an ADMIN (open).
- After that, registration requires a valid, unused single-use invite code.
- Admins create invites (optionally pre-setting email + role).
"""
from functools import wraps

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort)
from flask_login import login_user, logout_user, login_required, current_user

from models import db, User, Invite, ROLES, user_count, utcnow

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD = 8


def admin_required(view):
    """Gate a view to admins only (assumes login_required already applied)."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------- register
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    first_user = user_count() == 0
    prefill_code = request.args.get("code", "")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = User.normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        code = request.form.get("code", "").strip()

        invite = None
        errors = []
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if len(password) < MIN_PASSWORD:
            errors.append(f"Password must be at least {MIN_PASSWORD} characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")

        if not first_user:
            invite = Invite.query.filter_by(code=code).first()
            if invite is None or invite.is_used:
                errors.append("A valid, unused invite code is required to register.")
            elif invite.email and User.normalize_email(invite.email) != email:
                errors.append("This invite was issued for a different email address.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", first_user=first_user,
                                   code=code or prefill_code, name=name, email=email), 400

        role = "admin" if first_user else (invite.role if invite else "facilitator")
        user = User(email=email, name=name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # assign user.id before consuming the invite

        if invite is not None:
            invite.used_by_id = user.id
            invite.used_at = utcnow()

        db.session.commit()
        login_user(user)
        flash("Welcome to Engage2Win." if first_user else "Account created.", "ok")
        return redirect(url_for("index"))

    return render_template("register.html", first_user=first_user, code=prefill_code)


# ---------------------------------------------------------------- login/logout
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = User.normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Incorrect email or password.", "error")
            return render_template("login.html", email=email), 401
        login_user(user)
        next_url = request.args.get("next")
        return redirect(next_url or url_for("index"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Signed out.", "ok")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------- invites (admin)
@auth_bp.route("/invites", methods=["GET", "POST"])
@admin_required
def invites():
    if request.method == "POST":
        email = User.normalize_email(request.form.get("email")) or None
        role = request.form.get("role", "facilitator")
        if role not in ROLES:
            role = "facilitator"
        invite = Invite(code=Invite.new_code(), email=email, role=role,
                        created_by_id=current_user.id)
        db.session.add(invite)
        db.session.commit()
        flash("Invite created.", "ok")
        return redirect(url_for("auth.invites"))

    all_invites = Invite.query.order_by(Invite.created_at.desc()).all()
    return render_template("invites.html", invites=all_invites,
                           register_base=url_for("auth.register", _external=True))
