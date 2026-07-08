"""Tests for Phase 4 map analysis routes."""
import json
import os
from pathlib import Path
import pytest
from app.server import app, db
from app.models import User, Customer, Session, MapAnalysis


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_user(client):
    """Create and authenticate a test user."""
    with app.app_context():
        u = User(email="test@test.com", name="Test User", role="facilitator")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
        user_id = u.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return user_id


@pytest.fixture
def session_with_customer(auth_user):
    """Create a customer and session for testing."""
    with app.app_context():
        u = User.query.get(auth_user)
        c = Customer(owner_user_id=u.id, name="Test Customer")
        db.session.add(c)
        db.session.commit()
        cid = c.id

        s = Session(customer_id=cid, owner_user_id=u.id, title="Test Session")
        db.session.add(s)
        db.session.commit()
        return cid, s.id


def test_map_list_requires_login(client):
    """Map list should redirect if not logged in."""
    rv = client.get("/sessions/1/maps")
    assert rv.status_code in (302, 401)  # Redirect or unauthorized


def test_map_list_404_cross_user(client, auth_user):
    """Map list should 404 for sessions not owned by user."""
    rv = client.get("/sessions/999/maps")
    assert rv.status_code == 404


def test_map_list_shows_empty_state(client, auth_user, session_with_customer):
    cid, sid = session_with_customer
    rv = client.get(f"/sessions/{sid}/maps")
    assert rv.status_code == 200
    assert b"No maps uploaded yet" in rv.data


def test_upload_map_invalid_type(client, auth_user, session_with_customer):
    """Upload with invalid map_type should show error."""
    cid, sid = session_with_customer
    data = {
        "map_type": "invalid_type",
        "image": (b"fake image", "test.jpg"),
    }
    rv = client.post(f"/sessions/{sid}/maps/upload", data=data, content_type="multipart/form-data")
    assert rv.status_code in (302, 400)  # Redirect or error


def test_upload_map_missing_image(client, auth_user, session_with_customer):
    """Upload without image should show error."""
    cid, sid = session_with_customer
    data = {
        "map_type": "vision_keywords",
    }
    rv = client.post(f"/sessions/{sid}/maps/upload", data=data, content_type="multipart/form-data")
    assert rv.status_code in (302, 400)


def test_upload_map_success(client, auth_user, session_with_customer):
    """Successful upload should create MapAnalysis record."""
    cid, sid = session_with_customer
    data = {
        "map_type": "vision_keywords",
        "participant_name": "Alice",
        "role_context": "Sponsor",
        "image": (b"fake image data", "test.jpg"),
    }
    rv = client.post(f"/sessions/{sid}/maps/upload", data=data, content_type="multipart/form-data")
    assert rv.status_code == 302  # Redirect to detail

    with app.app_context():
        m = MapAnalysis.query.filter(MapAnalysis.session_id == sid).first()
        assert m is not None
        assert m.map_type == "vision_keywords"
        assert m.participant_name == "Alice"
        assert m.role_context == "Sponsor"


def test_map_detail_shows_mechanics(client, auth_user, session_with_customer):
    """Map detail should show mechanics for the map type."""
    cid, sid = session_with_customer

    with app.app_context():
        m = MapAnalysis(
            session_id=sid,
            map_type="vision_keywords",
            image_path="/tmp/test.jpg",
            eval_json="{}",
            band="",
        )
        db.session.add(m)
        db.session.commit()
        mid = m.id

    rv = client.get(f"/sessions/{sid}/maps/{mid}")
    assert rv.status_code == 200
    assert b"Vision Keywords Map" in rv.data
    assert b"Purpose" in rv.data
    assert b"Pending" in rv.data or b"PENDING" in rv.data


def test_map_detail_shows_results(client, auth_user, session_with_customer):
    """Map detail should show analysis results when available."""
    cid, sid = session_with_customer

    eval_data = {
        "overall": 75,
        "verdict": {"title": "Good map", "text": "Well organized"},
        "dimensions": [],
        "language": "en",
    }

    with app.app_context():
        m = MapAnalysis(
            session_id=sid,
            map_type="vision_keywords",
            image_path="/tmp/test.jpg",
            eval_json=json.dumps(eval_data),
            band="green",
        )
        db.session.add(m)
        db.session.commit()
        mid = m.id

    rv = client.get(f"/sessions/{sid}/maps/{mid}")
    assert rv.status_code == 200
    assert b"75" in rv.data  # Score shown
    assert b"Good map" in rv.data  # Title shown


def test_delete_map(client, auth_user, session_with_customer):
    """Delete should remove map from database."""
    cid, sid = session_with_customer

    with app.app_context():
        m = MapAnalysis(
            session_id=sid,
            map_type="vision_keywords",
            image_path="/tmp/test.jpg",
            eval_json="{}",
            band="",
        )
        db.session.add(m)
        db.session.commit()
        mid = m.id

    rv = client.post(f"/sessions/{sid}/maps/{mid}/delete")
    assert rv.status_code == 302

    with app.app_context():
        m = MapAnalysis.query.get(mid)
        assert m is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
