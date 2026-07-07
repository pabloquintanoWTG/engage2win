"""Database models for Engage2Win (Phase 1: auth + data layer).

SQLite via Flask-SQLAlchemy. Phase 1 defines only the account layer — User and
Invite. Customers/Sessions/etc. arrive in later phases (see docs/prd).
"""
import secrets
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ROLES = ("facilitator", "admin")


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False, default="")
    role = db.Column(db.String(20), nullable=False, default="facilitator")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # --- password helpers (never store plaintext) ---
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @staticmethod
    def normalize_email(email):
        return (email or "").strip().lower()

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Invite(db.Model):
    """Single-use invitation. Created by an admin; consumed at registration."""
    __tablename__ = "invites"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)          # optional pre-fill
    role = db.Column(db.String(20), nullable=False, default="facilitator")
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    used_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    used_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    used_by = db.relationship("User", foreign_keys=[used_by_id])

    @property
    def is_used(self):
        return self.used_by_id is not None

    @staticmethod
    def new_code():
        return secrets.token_urlsafe(12)

    def __repr__(self):
        status = "used" if self.is_used else "open"
        return f"<Invite {self.code} ({status})>"


def user_count():
    """How many users exist — used to decide first-user-is-admin vs invite-required."""
    return db.session.query(User).count()


# ---------------------------------------------------------------- Phase 2 models
LANGUAGES = ("en", "es", "ca")
SESSION_STATUSES = ("planned", "running", "complete")


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(255), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    owner = db.relationship("User")
    sessions = db.relationship("Session", back_populates="customer",
                               cascade="all, delete-orphan", order_by="Session.created_at.desc()")

    def __repr__(self):
        return f"<Customer {self.name}>"


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    objectives = db.Column(db.Text, nullable=False, default="")
    language = db.Column(db.String(5), nullable=False, default="en")
    scheduled_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="planned")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    customer = db.relationship("Customer", back_populates="sessions")
    owner = db.relationship("User")
    participants = db.relationship("Participant", back_populates="session",
                                   cascade="all, delete-orphan", order_by="Participant.id")

    def __repr__(self):
        return f"<Session {self.title} ({self.status})>"


class Participant(db.Model):
    __tablename__ = "participants"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    role_dept = db.Column(db.String(255), nullable=False, default="")
    email = db.Column(db.String(255), nullable=True)

    session = db.relationship("Session", back_populates="participants")

    def __repr__(self):
        return f"<Participant {self.name}>"


def owned(model, user):
    """Query helper: rows owned by `user`, or all rows if the user is an admin.
    Applies to any model with an `owner_user_id` column (Customer, Session)."""
    q = model.query
    if getattr(user, "is_admin", False):
        return q
    return q.filter(model.owner_user_id == user.id)
