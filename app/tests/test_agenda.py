"""Phase 3 tests: agenda builder (CRUD, ownership, time budget, validation).
DB reset per test by conftest._fresh_db (autouse)."""
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402
from models import db, Customer, Session, AgendaItem  # noqa: E402


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


def _create_session(client, customer_id, title="Vision Workshop"):
    r = client.post(
        f"/customers/{customer_id}/sessions",
        data={"title": title, "objectives": "Define supply chain vision", "language": "en"}
    )
    assert r.status_code in (200, 302)
    with server.app.app_context():
        return Session.query.filter_by(title=title).first().id


def test_create_agenda_item():
    """POST /sessions/<id>/agenda creates an agenda item."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    response = c.post(
        f'/sessions/{sid}/agenda',
        data={
            'type': 'section',
            'name': 'Visioning',
            'category': 'Vision',
            'duration_min': 45,
            'description': 'Uncover vision keywords',
            'activities': 'Keyword writing\nClustering\nVoting',
            'tips': 'Let sponsor vote last\nLimit to 5 clusters',
            'roles': 'Facilitator, All participants',
            'materials': 'Sticky notes, markers',
            'output': 'Prioritized vision keywords',
            'map_type': 'vision_keywords',
            'enabled': 'on'
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'Agenda item added' in response.data

    # Verify item was created
    with server.app.app_context():
        item = AgendaItem.query.filter_by(name='Visioning').first()
        assert item is not None
        assert item.position == 0
        assert item.duration_min == 45
        assert item.map_type == 'vision_keywords'
        assert item.enabled is True
        assert item.get_activities() == ['Keyword writing', 'Clustering', 'Voting']
        assert item.get_tips() == ['Let sponsor vote last', 'Limit to 5 clusters']


def test_list_agenda_items():
    """GET /sessions/<id>/agenda lists all items in order."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    # Create 3 items via DB
    with server.app.app_context():
        for i, (name, duration) in enumerate([('Welcome', 15), ('Visioning', 45), ('Break', 15)]):
            item = AgendaItem(
                session_id=sid, position=i, type='section',
                name=name, category='Vision', duration_min=duration
            )
            db.session.add(item)
        db.session.commit()

    response = c.get(f'/sessions/{sid}/agenda')
    assert response.status_code == 200
    assert b'Welcome' in response.data
    assert b'Visioning' in response.data
    assert b'Break' in response.data
    # 15 + 45 + 15 = 75 minutes = 1h 15m
    assert b'1h 15m' in response.data or b'75m' in response.data  # Total time


def test_edit_agenda_item():
    """POST /sessions/<id>/agenda/<aid>/edit updates an item."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    # Create item
    with server.app.app_context():
        item = AgendaItem(
            session_id=sid, position=0, type='section',
            name='Visioning', category='Vision', duration_min=45
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = c.post(
        f'/sessions/{sid}/agenda/{item_id}/edit',
        data={
            'type': 'section',
            'name': 'Visioning & Ambitions',
            'category': 'Vision',
            'duration_min': 60,
            'map_type': 'vision_keywords',
            'enabled': 'on'
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'Agenda item updated' in response.data

    # Verify update
    with server.app.app_context():
        item = AgendaItem.query.get(item_id)
        assert item.name == 'Visioning & Ambitions'
        assert item.duration_min == 60


def test_delete_agenda_item():
    """POST /sessions/<id>/agenda/<aid>/delete removes an item."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    # Create item
    with server.app.app_context():
        item = AgendaItem(
            session_id=sid, position=0, type='section',
            name='Visioning', category='Vision', duration_min=45
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = c.post(
        f'/sessions/{sid}/agenda/{item_id}/delete',
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'Agenda item deleted' in response.data

    # Verify deletion
    with server.app.app_context():
        assert AgendaItem.query.get(item_id) is None


def test_reorder_agenda_items():
    """POST /sessions/<id>/agenda/reorder reorders items."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    # Create 3 items
    with server.app.app_context():
        items = []
        for i, name in enumerate(['Item A', 'Item B', 'Item C']):
            item = AgendaItem(
                session_id=sid, position=i, type='section',
                name=name, category='Vision', duration_min=30
            )
            db.session.add(item)
            items.append(item)
        db.session.commit()
        item_ids = [item.id for item in items]

    # Reorder: B, C, A
    response = c.post(
        f'/sessions/{sid}/agenda/reorder',
        data=json.dumps({
            'items': [
                {'id': item_ids[1], 'position': 0},
                {'id': item_ids[2], 'position': 1},
                {'id': item_ids[0], 'position': 2}
            ]
        }),
        content_type='application/json'
    )
    assert response.status_code == 200

    # Verify reorder
    with server.app.app_context():
        items_after = AgendaItem.query.filter(
            AgendaItem.id.in_(item_ids)).order_by(AgendaItem.id).all()
        assert items_after[0].position == 2
        assert items_after[1].position == 0
        assert items_after[2].position == 1


def test_user_cannot_access_other_users_agenda():
    """User B cannot access User A's session's agenda (404)."""
    admin = _admin_client()
    cid = _create_customer(admin)
    sid = _create_session(admin, cid)

    # Create another user (facilitator)
    fac = _invited_client(admin, "fac@test.com")

    # Try to access admin's session as facilitator
    response = fac.get(f'/sessions/{sid}/agenda', follow_redirects=False)
    assert response.status_code == 404


def test_user_cannot_edit_other_users_agenda_item():
    """User B cannot edit User A's agenda item (404)."""
    admin = _admin_client()
    cid = _create_customer(admin)
    sid = _create_session(admin, cid)

    # Create item in admin's session
    with server.app.app_context():
        item = AgendaItem(session_id=sid, position=0, type='section',
                          name='Visioning', category='Vision', duration_min=45)
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    # Create another user (facilitator)
    fac = _invited_client(admin, "fac@test.com")

    # Try to edit as facilitator
    response = fac.post(
        f'/sessions/{sid}/agenda/{item_id}/edit',
        data={'name': 'Hacked', 'category': 'Vision', 'type': 'section',
              'duration_min': 45},
        follow_redirects=False
    )
    assert response.status_code == 404


def test_create_with_missing_name():
    """POST with empty name returns 400."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    response = c.post(
        f'/sessions/{sid}/agenda',
        data={
            'type': 'section',
            'name': '',
            'category': 'Vision',
            'duration_min': 45
        },
        follow_redirects=True
    )
    assert response.status_code == 400
    assert b'Name is required' in response.data


def test_create_with_invalid_category():
    """POST with invalid category returns 400."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    response = c.post(
        f'/sessions/{sid}/agenda',
        data={
            'type': 'section',
            'name': 'Visioning',
            'category': 'InvalidCategory',
            'duration_min': 45
        },
        follow_redirects=True
    )
    assert response.status_code == 400
    assert b'Invalid category' in response.data


def test_create_with_zero_duration():
    """POST with duration <= 0 returns 400."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    response = c.post(
        f'/sessions/{sid}/agenda',
        data={
            'type': 'section',
            'name': 'Visioning',
            'category': 'Vision',
            'duration_min': 0
        },
        follow_redirects=True
    )
    assert response.status_code == 400
    # HTML-encoded version of the error message
    assert b'Duration must be &gt; 0' in response.data or b'Duration must be > 0' in response.data


def test_create_with_invalid_map_type():
    """POST with invalid map_type returns 400."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    response = c.post(
        f'/sessions/{sid}/agenda',
        data={
            'type': 'section',
            'name': 'Visioning',
            'category': 'Vision',
            'duration_min': 45,
            'map_type': 'invalid_map_type'
        },
        follow_redirects=True
    )
    assert response.status_code == 400
    assert b'Invalid map type' in response.data


def test_time_budget_calculation():
    """Total time is sum of enabled items."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    with server.app.app_context():
        items = [
            AgendaItem(session_id=sid, position=0, type='section',
                       name='Visioning', category='Vision', duration_min=45, enabled=True),
            AgendaItem(session_id=sid, position=1, type='break',
                       name='Break', category='Intro / Closing', duration_min=15, enabled=True),
            AgendaItem(session_id=sid, position=2, type='section',
                       name='Problem Statements', category='Problem', duration_min=45, enabled=False),
        ]
        for item in items:
            db.session.add(item)
        db.session.commit()

    response = c.get(f'/sessions/{sid}/agenda')
    assert response.status_code == 200
    # Only enabled items: 45 + 15 = 60 minutes = 1h 0m
    # Check for the time in the budget display (may be formatted as "1h" only if no minutes)
    assert b'Total: 1h' in response.data


def test_api_agenda_returns_timeline():
    """GET /api/sessions/<id>/agenda returns start/end times."""
    c = _admin_client()
    cid = _create_customer(c)
    sid = _create_session(c, cid)

    with server.app.app_context():
        items = [
            AgendaItem(session_id=sid, position=0, type='section',
                       name='Welcome', category='Intro / Closing', duration_min=15, enabled=True),
            AgendaItem(session_id=sid, position=1, type='section',
                       name='Visioning', category='Vision', duration_min=45, enabled=True),
        ]
        for item in items:
            db.session.add(item)
        db.session.commit()

    response = c.get(f'/api/sessions/{sid}/agenda')
    assert response.status_code == 200
    data = response.get_json()

    assert data['total_minutes'] == 60
    assert len(data['timeline']) == 2
    assert data['timeline'][0]['start_time'] == '09:00'
    assert data['timeline'][0]['end_time'] == '09:15'
    assert data['timeline'][1]['start_time'] == '09:15'
    assert data['timeline'][1]['end_time'] == '10:00'


def test_get_sections_api():
    """GET /api/sections returns section library."""
    c = _admin_client()

    response = c.get('/api/sections')
    assert response.status_code == 200
    data = response.get_json()
    assert 'sections' in data
    assert 'categories' in data
    assert len(data['sections']) == 14  # 14 sections in DEFAULT_SECTIONS
    assert 'Vision' in data['categories']
