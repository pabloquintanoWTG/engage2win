"""Tests for the Phase 1 Flask app. The claude CLI is mocked everywhere — no
real model calls, no network. We exercise routes, the background worker, and
the RAG rendering on the result page."""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
import server  # noqa: E402

VALID_EVAL = {
    "overall": 74,
    "verdict": {"band": "green", "title": "Strong map", "text": "Clear value chain."},
    "dimensions": [
        {"key": "detail", "score": 70, "comment": "Specific notes."},
        {"key": "insight", "score": 62, "comment": "Some connections."},
        {"key": "clarity", "score": 82, "comment": "Legible."},
        {"key": "innovation", "score": 58, "comment": "Conventional."},
        {"key": "rigor", "score": 66, "comment": "Mostly grounded."},
    ],
    "strengths": ["Clear flow"],
    "recommendations": ["Add arrows"],
    "questions": ["What is the key trade-off?"],
    "confidence": "medium",
    "language": "en",
}


@pytest.fixture
def client(_fresh_db):
    """A logged-in client. The first registration becomes the admin, so all the
    analyzer routes (now behind @login_required) are reachable."""
    server.app.config.update(TESTING=True)
    c = server.app.test_client()
    r = c.post("/register", data={
        "name": "Tester", "email": "tester@example.com",
        "password": "password123", "confirm": "password123"})
    assert r.status_code in (200, 302)
    return c


def _png():
    # minimal but real-enough bytes; extension is what the route checks
    return (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "map.png")


def test_index_renders_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Analyze an engage2win map" in r.data
    assert b'name="image"' in r.data


def test_analyze_rejects_missing_file(client):
    r = client.post("/analyze", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert b"choose a map photo" in r.data


def test_analyze_rejects_bad_extension(client):
    data = {"image": (io.BytesIO(b"hello"), "notes.txt")}
    r = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert r.status_code == 400


def test_oversized_upload_returns_json_413(client):
    # shrink the cap so we don't have to ship 20 MB through the test
    server.app.config["MAX_CONTENT_LENGTH"] = 64
    try:
        data = {"image": (io.BytesIO(b"0" * 4096), "big.png")}
        r = client.post("/analyze", data=data, content_type="multipart/form-data")
        assert r.status_code == 413
        assert r.is_json and "too large" in r.get_json()["error"].lower()
    finally:
        server.app.config["MAX_CONTENT_LENGTH"] = server.MAX_BYTES


def test_analyze_starts_job_and_returns_id(client):
    # block the worker thread so we only test the route's response
    with patch.object(server.threading, "Thread"):
        data = {"image": _png(), "language": "en", "name": "ACME"}
        r = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert r.status_code == 202
    assert "job_id" in r.get_json()


def test_happy_path_worker_and_result(client):
    # run the worker synchronously with the CLI mocked, then render the result
    with patch.object(server.run, "call_model_cli", return_value=json.dumps(VALID_EVAL)), \
         patch.object(server.run, "describe_map_cli", return_value="## Map\nLooks good."), \
         patch.object(server.threading, "Thread") as Thread:
        data = {"image": _png(), "language": "en"}
        r = client.post("/analyze", data=data, content_type="multipart/form-data")
        job_id = r.get_json()["job_id"]
        # run the worker that the (mocked) Thread would have started
        server.run_job(*Thread.call_args.kwargs["args"])

    # status should be done
    s = client.get(f"/status/{job_id}").get_json()
    assert s["state"] == "done"
    assert s["result_url"].endswith(job_id)

    # result page renders RAG + verdict + editable + description copy
    res = client.get(f"/result/{job_id}")
    assert res.status_code == 200
    body = res.data.decode()
    assert "rag-ball green" in body          # overall 74 -> green
    assert "Strong map" in body
    assert 'contenteditable="true"' in body  # editable output
    assert "id=\"copyDesc\"" in body          # copy icon on description
    assert "AMBER" in body or "RED" in body   # dimension bands rendered


def test_schema_invalid_sets_error(client):
    bad = {"overall": 74}  # missing required fields
    with patch.object(server.run, "call_model_cli", return_value=json.dumps(bad)), \
         patch.object(server.run, "describe_map_cli", return_value="x"), \
         patch.object(server.threading, "Thread") as Thread:
        data = {"image": _png(), "language": "en"}
        r = client.post("/analyze", data=data, content_type="multipart/form-data")
        job_id = r.get_json()["job_id"]
        server.run_job(*Thread.call_args.kwargs["args"])

    s = client.get(f"/status/{job_id}").get_json()
    assert s["state"] == "error"
    assert "schema" in s["error"].lower()
    assert client.get(f"/result/{job_id}").status_code == 404
