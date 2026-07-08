"""Database models for Engage2Win (Phase 1: auth + data layer).

SQLite via Flask-SQLAlchemy. Phase 1 defines only the account layer — User and
Invite. Customers/Sessions/etc. arrive in later phases (see docs/prd).
"""
import json
import secrets
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ROLES = ("facilitator", "admin")
MAP_TYPES = ("vision_keywords", "problem_statements", "metrics_root_cause",
             "capability_map", "criteria", "capability_ranking", "roadmap")
AGENDA_TYPES = ("section", "break", "intro")
CATEGORIES = (
    "Inspire", "Vision", "Value", "Problem", "Capability", "Prioritise",
    "Next steps", "Intro / Closing", "Custom"
)


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
    agenda_items = db.relationship("AgendaItem", back_populates="session",
                                   cascade="all, delete-orphan", order_by="AgendaItem.position")
    map_analyses = db.relationship("MapAnalysis", back_populates="session",
                                   cascade="all, delete-orphan", order_by="MapAnalysis.created_at.desc()")

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


# ---------------------------------------------------------------- Phase 3 models
class AgendaItem(db.Model):
    __tablename__ = "agenda_items"
    __table_args__ = (db.UniqueConstraint('session_id', 'position', name='uq_session_position'),)

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(20), nullable=False, default="section")
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(255), nullable=False)
    duration_min = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    activities = db.Column(db.Text, nullable=False, default="[]")  # JSON
    tips = db.Column(db.Text, nullable=False, default="[]")  # JSON
    roles = db.Column(db.String(255), nullable=False, default="")
    materials = db.Column(db.String(255), nullable=False, default="")
    output = db.Column(db.String(255), nullable=False, default="")
    map_type = db.Column(db.String(20), nullable=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    session = db.relationship("Session", back_populates="agenda_items")

    def get_activities(self):
        try:
            return json.loads(self.activities)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_tips(self):
        try:
            return json.loads(self.tips)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_activities(self, activities):
        self.activities = json.dumps(activities or [])

    def set_tips(self, tips):
        self.tips = json.dumps(tips or [])

    def __repr__(self):
        return f"<AgendaItem {self.name} (pos {self.position})>"


# ---------------------------------------------------------------- Phase 4 models
class MapAnalysis(db.Model):
    __tablename__ = "map_analyses"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    agenda_item_id = db.Column(db.Integer, db.ForeignKey("agenda_items.id"), nullable=True, index=True)
    map_type = db.Column(db.String(20), nullable=False)
    image_path = db.Column(db.String(512), nullable=False)
    participant_name = db.Column(db.String(255), nullable=True)
    role_context = db.Column(db.String(512), nullable=True)
    eval_json = db.Column(db.Text, nullable=False)  # Full evaluation JSON from Phase 0
    description_md = db.Column(db.Text, nullable=False, default="")
    band = db.Column(db.String(10), nullable=True)  # green|amber|red (NULL = not evaluated)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending|running|done|error
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    session = db.relationship("Session", back_populates="map_analyses")
    agenda_item = db.relationship("AgendaItem")

    def __repr__(self):
        return f"<MapAnalysis {self.map_type} ({self.band})>"


def owned(model, user):
    """Query helper: rows owned by `user`, or all rows if the user is an admin.
    Applies to any model with an `owner_user_id` column (Customer, Session)."""
    q = model.query
    if getattr(user, "is_admin", False):
        return q
    return q.filter(model.owner_user_id == user.id)


# ---------------------------------------------------------------- Map mechanics (Phase 4)
MAP_MECHANICS = {
    "vision_keywords": {
        "name": "Vision Keywords Map",
        "purpose": "Capture the DNA of the customer's supply-chain vision as keywords and reach consensus on the few that matter.",
        "mechanics": [
            "Each participant writes 1–2-word keywords in silence (3–5 minutes)",
            "Facilitator captures and clusters similar keywords on a shared map",
            "Participants explain each cluster",
            "Dot voting: 3 votes per participant (sponsor votes last to avoid anchoring bias)",
            "Confirm consensus on 3–5 clusters"
        ],
        "expected_output": "A prioritised keyword map with 3–5 validated clusters the group agrees define the vision",
        "evaluation_signals": [
            "Keywords are concise (not sentences)",
            "Clear clustering logic",
            "Manageable 3–5 clusters (not sprawl)",
            "Evidence of prioritisation/voting",
            "Sponsor influence visible",
            "Clusters genuinely express a shared vision"
        ]
    },
    "problem_statements": {
        "name": "Problem Statements Map",
        "purpose": "Validate interview insights and reach consensus on the most important problems blocking the vision.",
        "mechanics": [
            "Present top ~20 problem statements (from interviews) on one view",
            "Discuss: 'Are you missing any? Which top 3 hinder the vision? Are they connected?'",
            "Optionally place statements against a Supply Chain map to locate where each problem hurts",
            "Facilitator stickies key insights and connections"
        ],
        "expected_output": "A validated, prioritised set of problem statements with a clear top 3, ideally connected to each other and to the supply chain",
        "evaluation_signals": [
            "Statements are real problems (not solutions in disguise)",
            "How-might-we framing present",
            "Top 3 identified and prioritised",
            "Connections/causality shown between problems",
            "Tied to the vision and to points on the supply chain"
        ]
    },
    "metrics_root_cause": {
        "name": "Metrics & Root-Cause Map (Value Tree)",
        "purpose": "Connect the vision to measurable business impact and expose the root causes behind the numbers.",
        "mechanics": [
            "Build a value tree: Key Metrics → Tier 2/3 metrics → root causes/problem statements",
            "Identify metrics that drive business impact (P&L)",
            "Map problem statements and root causes that affect each metric",
            "Teams work in 2 groups (~30 min) then compare maps"
        ],
        "expected_output": "A single-pane view from KPIs down to root causes and consequences, linked to P&L impact",
        "evaluation_signals": [
            "Metrics tie to business/P&L impact (not vanity metrics)",
            "Clear cause→effect chains",
            "Root causes reach real drivers (5-why depth), not surface symptoms",
            "Tier 2/3 metrics connect up to the key metric",
            "Coverage across supply chain functions"
        ]
    }
}


# ---------------------------------------------------------------- Section library
DEFAULT_SECTIONS = [
    {"id": "welcome", "type": "intro", "name": "Welcome & introductions", "category": "Intro / Closing", "minutes": 15, "enabled": True, "description": "Welcome participants, set the scene, introductions round, ground rules, and agenda walkthrough.", "activities": ["Sponsor welcome (2 min)", "Participant introductions round", "Ground rules & ways of working", "Agenda overview"], "tips": ["Keep intros to name + role + one expectation", "Display the agenda visually on a wall poster", "Establish a 'parking lot' for off-topic items"], "roles": "Sponsor (welcome), Facilitator (agenda)", "materials": "Printed agenda, name tents, ground rules poster", "output": "Aligned group with clear expectations", "map_type": None},
    {"id": "outside_in", "type": "section", "name": "Outside-in perspectives", "category": "Inspire", "minutes": 45, "enabled": True, "description": "Bring external expertise and inspiration to the group before diving into visioning.", "activities": ["Industry landscape & trends overview (presenter)", "Emerging operating models showcase", "Technology & AI innovation spotlight", "Provocations & 'what if' questions", "Open Q&A and reflection"], "tips": ["Tailor content to the customer's industry", "Use real examples and case studies, not theory", "Keep it concise and energising", "End with 2-3 provocative questions"], "roles": "Presenter / SME (lead), Facilitator (moderator), All participants", "materials": "Presentation deck (tailored), industry benchmarks, printed key stats", "output": "Inspired group with shared external context", "map_type": None},
    {"id": "visioning", "type": "section", "name": "Visioning & ambitions", "category": "Vision", "minutes": 45, "enabled": True, "description": "Uncover the customer's supply chain vision. Align the team around aspirational keywords.", "activities": ["Silent keyword writing (individual)", "Keyword clustering on vision map", "Dot voting on top themes", "Consensus check & lock-in"], "tips": ["Let the sponsor vote last to avoid anchoring bias", "If >5 clusters emerge, force a prioritisation round", "Keep it simple - no explanations, just keywords"], "roles": "Facilitator (lead), Sponsor (last voter), All participants", "materials": "Vision keyword map (A0 poster), sticky notes, dot stickers, sharpies", "output": "Prioritised vision keyword map with 3-5 validated clusters", "map_type": "vision_keywords"},
    {"id": "value_drivers", "type": "section", "name": "Value drivers", "category": "Value", "minutes": 45, "enabled": True, "description": "Map strategic value imperatives that connect vision to measurable business outcomes.", "activities": ["Value tree introduction (facilitator)", "Small group value mapping exercise", "Cross-group share-back & challenge", "Value driver prioritisation"], "tips": ["Use the value tree template to keep groups on track", "Challenge vague drivers - push for specificity", "Link every driver back to the vision keywords"], "roles": "Facilitator, Small groups (3-4 per group), Note-taker per group", "materials": "Value tree templates (A1), markers, timer", "output": "Completed value tree with ranked strategic drivers", "map_type": None},
    {"id": "break_morning", "type": "break", "name": "Morning break", "category": "Intro / Closing", "minutes": 15, "enabled": True, "description": "Coffee break - allow networking and informal discussion.", "activities": [], "tips": ["Have coffee/tea ready before the break starts"], "roles": "All participants", "materials": "Refreshments", "output": "", "map_type": None},
    {"id": "fishbone", "type": "section", "name": "Fishbone analysis", "category": "Problem", "minutes": 60, "enabled": True, "description": "Root cause identification using Ishikawa diagram methodology to surface systemic issues.", "activities": ["Problem statement framing", "Category brainstorm (6M framework)", "Root cause deep-dive per category", "Cross-pollination & pattern identification"], "tips": ["Don't let the group jump to solutions", "Use the 5-Why technique if causes are too surface-level"], "roles": "Facilitator, Category leads (1 per arm), All participants rotating", "materials": "Fishbone template (A0), coloured sticky notes per category, markers", "output": "Completed fishbone diagram with prioritised root causes", "map_type": None},
    {"id": "problem_statements", "type": "section", "name": "Problem statements", "category": "Problem", "minutes": 45, "enabled": True, "description": "Transform fishbone outputs into clear, actionable problem statements.", "activities": ["Problem statement writing (individual)", "Peer review & refinement in pairs", "Group validation & deduplication", "Final statement selection"], "tips": ["Use 'How might we...' format", "Reject statements that are solutions in disguise"], "roles": "Facilitator, All participants (individual + pairs)", "materials": "Problem statement cards, pens, validation checklist", "output": "5-8 validated, actionable problem statements", "map_type": "problem_statements"},
    {"id": "break_lunch", "type": "break", "name": "Lunch break", "category": "Intro / Closing", "minutes": 45, "enabled": True, "description": "Lunch break - encourage informal networking.", "activities": [], "tips": ["Announce restart time clearly before break"], "roles": "All participants", "materials": "Lunch catering", "output": "", "map_type": None},
    {"id": "capability_review", "type": "section", "name": "Capability review", "category": "Capability", "minutes": 60, "enabled": True, "description": "Evaluate existing and required capabilities against problem statements and value drivers.", "activities": ["Capability mapping introduction", "Current-state assessment", "Target-state definition", "Gap analysis & heat mapping"], "tips": ["Use capability maturity model (1-5 scale)", "Focus on capabilities, not tools"], "roles": "Facilitator, Domain experts, All participants", "materials": "Capability matrix template, heat map stickers, scoring guide", "output": "Capability gap heat map with priority areas", "map_type": None},
    {"id": "criteria", "type": "section", "name": "Criteria definition", "category": "Prioritise", "minutes": 30, "enabled": True, "description": "Establish and weight evaluation criteria for prioritising initiatives.", "activities": ["Criteria brainstorm", "Criteria grouping & selection", "Pairwise weighting exercise", "Criteria validation"], "tips": ["Limit to 5-7 criteria maximum", "Get sponsor buy-in on weightings"], "roles": "Facilitator, Sponsor (validation), All participants", "materials": "Criteria cards, weighting matrix", "output": "Weighted evaluation criteria set (5-7 criteria)", "map_type": "criteria"},
    {"id": "break_afternoon", "type": "break", "name": "Afternoon break", "category": "Intro / Closing", "minutes": 15, "enabled": True, "description": "Short coffee break to recharge.", "activities": [], "tips": ["Keep it short - energy dips here"], "roles": "All participants", "materials": "Refreshments", "output": "", "map_type": None},
    {"id": "prioritisation", "type": "section", "name": "Prioritisation & ranking", "category": "Prioritise", "minutes": 60, "enabled": True, "description": "Score and rank initiatives against weighted criteria.", "activities": ["Initiative scoring (individual)", "Score calibration discussion", "Ranking matrix completion", "Top-5 deep dive & validation"], "tips": ["Use silent scoring first, then discuss outliers", "The sponsor breaks ties, not the facilitator"], "roles": "Facilitator, Sponsor (tie-breaker), All participants (scorers)", "materials": "Scoring matrix, calculators, ranking board", "output": "Prioritised initiative ranking with scores and rationale", "map_type": "capability_ranking"},
    {"id": "next_steps", "type": "section", "name": "Next steps & roadmap", "category": "Next steps", "minutes": 30, "enabled": True, "description": "Define action items, assign owners, build implementation timeline.", "activities": ["Action item definition per initiative", "Owner assignment & commitment", "Timeline mapping (30/60/90 day)", "Closing round & reflections"], "tips": ["Every action needs an owner AND a deadline", "Don't overcommit - focus on top 3-5 actions"], "roles": "Facilitator, Sponsor (commitment), All participants (owners)", "materials": "Action plan template, timeline board, commitment cards", "output": "Signed-off action plan with owners, deadlines, and 90-day roadmap", "map_type": "roadmap"},
    {"id": "closing", "type": "intro", "name": "Closing & reflections", "category": "Intro / Closing", "minutes": 15, "enabled": True, "description": "Wrap up with reflections, key takeaways, and thank-yous.", "activities": ["One-word checkout round", "Sponsor closing remarks", "Feedback form distribution", "Photo & thank-yous"], "tips": ["Keep it positive - end on energy", "Confirm follow-up meeting date before people leave"], "roles": "Facilitator, Sponsor", "materials": "Feedback forms, camera", "output": "Participant reflections and feedback collected", "map_type": None},
]
