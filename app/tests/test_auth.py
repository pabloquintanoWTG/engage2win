"""Auth + invite tests. DB is reset per test by conftest._fresh_db (autouse)."""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402
from models import db, User, Invite  # noqa: E402


def _register(client, email, password="password123", name="U", code=None):
    data = {"name": name, "email": email, "password": password, "confirm": password}
    if code is not None:
        data["code"] = code
    return client.post("/register", data=data)


def _invite_code():
    with server.app.app_context():
        return Invite.query.first().code


def test_first_user_becomes_admin():
    c = server.app.test_client()
    r = _register(c, "admin@example.com")
    assert r.status_code in (200, 302)
    with server.app.app_context():
        u = User.query.filter_by(email="admin@example.com").first()
        assert u is not None
        assert u.role == "admin"
        assert u.password_hash and u.password_hash != "password123"  # hashed
        assert u.check_password("password123")


def test_duplicate_email_rejected():
    c = server.app.test_client()
    _register(c, "admin@example.com")
    c.post("/logout")
    r = _register(server.app.test_client(), "admin@example.com")
    assert r.status_code == 400


def test_weak_password_rejected():
    c = server.app.test_client()
    r = _register(c, "admin@example.com", password="short")
    assert r.status_code == 400
    with server.app.app_context():
        assert User.query.count() == 0


def test_second_registration_requires_invite():
    admin = server.app.test_client()
    _register(admin, "admin@example.com")           # first -> admin, logged in

    visitor = server.app.test_client()
    denied = _register(visitor, "user@example.com")  # no code
    assert denied.status_code == 400

    created = admin.post("/invites", data={"email": "", "role": "facilitator"})
    assert created.status_code in (200, 302)

    ok = _register(visitor, "user@example.com", code=_invite_code())
    assert ok.status_code in (200, 302)
    with server.app.app_context():
        u = User.query.filter_by(email="user@example.com").first()
        assert u.role == "facilitator"
        assert Invite.query.first().is_used


def test_invite_is_single_use():
    admin = server.app.test_client()
    _register(admin, "admin@example.com")
    admin.post("/invites", data={"email": "", "role": "facilitator"})
    code = _invite_code()

    first = _register(server.app.test_client(), "one@example.com", code=code)
    assert first.status_code in (200, 302)
    reused = _register(server.app.test_client(), "two@example.com", code=code)
    assert reused.status_code == 400


def test_login_logout_and_bad_password():
    c = server.app.test_client()
    _register(c, "admin@example.com")
    c.post("/logout")

    bad = c.post("/login", data={"email": "admin@example.com", "password": "nope"})
    assert bad.status_code == 401
    good = c.post("/login", data={"email": "admin@example.com", "password": "password123"})
    assert good.status_code in (200, 302)


def test_login_ignores_external_next_redirect():
    """Open-redirect guard: an external ?next must not be honoured."""
    c = server.app.test_client()
    _register(c, "admin@example.com")
    c.post("/logout")
    r = c.post("/login?next=https://evil.example.com/steal",
              data={"email": "admin@example.com", "password": "password123"})
    assert r.status_code == 302
    assert "evil.example.com" not in r.headers["Location"]
    # a local next is still honoured
    r2 = c.post("/login?next=/result/abc",
               data={"email": "admin@example.com", "password": "password123"})
    # (already authenticated now → app redirects home, but must never be external)
    assert "evil.example.com" not in r2.headers.get("Location", "")


def test_unauthenticated_page_redirects_and_api_401():
    c = server.app.test_client()
    page = c.get("/")
    assert page.status_code == 302
    assert "/login" in page.headers["Location"]

    api = c.post("/analyze", data={})
    assert api.status_code == 401
    assert api.is_json


def test_non_admin_cannot_access_invites():
    admin = server.app.test_client()
    _register(admin, "admin@example.com")
    admin.post("/invites", data={"email": "fac@example.com", "role": "facilitator"})

    fac = server.app.test_client()
    _register(fac, "fac@example.com", code=_invite_code())  # logged in as facilitator
    assert fac.get("/invites").status_code == 403


def test_seed_creates_admin():
    import seed
    rc = seed.main(["seedadmin@example.com", "password123", "Seed Admin"])
    assert rc == 0
    with server.app.app_context():
        u = User.query.filter_by(email="seedadmin@example.com").first()
        assert u is not None and u.role == "admin"
