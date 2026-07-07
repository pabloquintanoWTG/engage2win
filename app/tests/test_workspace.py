"""Phase 2 tests: customers, sessions, participants + ownership scoping.
DB reset per test by conftest._fresh_db (autouse)."""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402
from models import db, Customer, Session, Participant  # noqa: E402


def _register(client, email, name="U", code=None):
    data = {"name": name, "email": email, "password": "password123", "confirm": "password123"}
    if code is not None:
        data["code"] = code
    return client.post("/register", data=data)


def _admin_client():
    """First registrant → admin, logged in."""
    c = server.app.test_client()
    _register(c, "admin@example.com", name="Admin")
    return c


def _invited_client(admin, email):
    """Create an invite as admin, register a facilitator with it (logged in)."""
    admin.post("/invites", data={"email": "", "role": "facilitator"})
    with server.app.app_context():
        from models import Invite
        code = Invite.query.order_by(Invite.id.desc()).first().code
    c = server.app.test_client()
    _register(c, email, name=email.split("@")[0], code=code)
    return c


def _create_customer(client, name="ACME"):
    r = client.post("/customers", data={"name": name, "industry": "Tech", "notes": ""})
    assert r.status_code in (200, 302)
    with server.app.app_context():
        return Customer.query.filter_by(name=name).first().id


# ---------------------------------------------------------------- customers
def test_create_and_list_customer():
    c = _admin_client()
    _create_customer(c, "ACME")
    listing = c.get("/customers")
    assert listing.status_code == 200
    assert b"ACME" in listing.data


def test_empty_customer_name_rejected():
    c = _admin_client()
    r = c.post("/customers", data={"name": "  ", "industry": ""})
    assert r.status_code == 400
    with server.app.app_context():
        assert Customer.query.count() == 0


# ---------------------------------------------------------------- sessions
def test_create_session_and_workspace_renders():
    c = _admin_client()
    cid = _create_customer(c)
    r = c.post(f"/customers/{cid}/sessions",
               data={"title": "Visioning", "objectives": "Align on vision", "language": "en"})
    assert r.status_code in (200, 302)
    with server.app.app_context():
        s = Session.query.filter_by(title="Visioning").first()
        assert s is not None and s.customer_id == cid
        sid = s.id
    page = c.get(f"/sessions/{sid}")
    assert page.status_code == 200
    assert b"Align on vision" in page.data


def test_session_status_edit_persists():
    c = _admin_client()
    cid = _create_customer(c)
    c.post(f"/customers/{cid}/sessions", data={"title": "S", "language": "en"})
    with server.app.app_context():
        sid = Session.query.first().id
    c.post(f"/sessions/{sid}/edit", data={"title": "S", "status": "running", "language": "en"})
    with server.app.app_context():
        assert db.session.get(Session, sid).status == "running"


# ---------------------------------------------------------------- participants
def test_add_and_remove_participant():
    c = _admin_client()
    cid = _create_customer(c)
    c.post(f"/customers/{cid}/sessions", data={"title": "S", "language": "en"})
    with server.app.app_context():
        sid = Session.query.first().id

    c.post(f"/sessions/{sid}/participants",
           data={"name": "Jane Doe", "role_dept": "VP SC", "email": "jane@acme.test"})
    with server.app.app_context():
        p = Participant.query.filter_by(name="Jane Doe").first()
        assert p is not None
        pid = p.id
    page = c.get(f"/sessions/{sid}")
    assert b"Jane Doe" in page.data

    c.post(f"/sessions/{sid}/participants/{pid}/delete")
    with server.app.app_context():
        assert db.session.get(Participant, pid) is None


def test_empty_participant_name_rejected():
    c = _admin_client()
    cid = _create_customer(c)
    c.post(f"/customers/{cid}/sessions", data={"title": "S", "language": "en"})
    with server.app.app_context():
        sid = Session.query.first().id
    c.post(f"/sessions/{sid}/participants", data={"name": "  "})
    with server.app.app_context():
        assert Participant.query.count() == 0


# ---------------------------------------------------------------- ownership
def test_facilitator_cannot_see_others_customer():
    admin = _admin_client()
    cid = _create_customer(admin, "AdminCorp")

    fac = _invited_client(admin, "fac@example.com")
    # not in their list
    listing = fac.get("/customers")
    assert b"AdminCorp" not in listing.data
    # direct access is 404 (not 403 — don't leak existence)
    assert fac.get(f"/customers/{cid}").status_code == 404


def test_facilitator_cannot_open_others_session():
    admin = _admin_client()
    cid = _create_customer(admin)
    admin.post(f"/customers/{cid}/sessions", data={"title": "Secret", "language": "en"})
    with server.app.app_context():
        sid = Session.query.first().id

    fac = _invited_client(admin, "fac@example.com")
    assert fac.get(f"/sessions/{sid}").status_code == 404


def test_admin_sees_all_customers():
    admin = _admin_client()
    fac = _invited_client(admin, "fac@example.com")
    _create_customer(fac, "FacCorp")           # facilitator's customer
    # admin lists customers -> sees the facilitator's too
    listing = admin.get("/customers")
    assert b"FacCorp" in listing.data
