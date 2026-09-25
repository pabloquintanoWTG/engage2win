"""Phase 4 tests: map analysis routes, live progress and user-facing errors.
DB reset per test by conftest._fresh_db (autouse)."""
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402
import workspace  # noqa: E402
from models import db, Customer, Session, MapAnalysis, MAP_MECHANICS  # noqa: E402
from analysis_status import explain_error, NoBackendError  # noqa: E402

app = server.app

VALID_EVAL = {
    "overall": 74,
    "verdict": {"band": "green", "title": "Strong map", "text": "Clear and specific."},
    "dimensions": [{"key": k, "score": 70, "comment": "ok"}
                   for k in ("detail", "insight", "clarity", "innovation", "rigor")],
    "strengths": ["a"], "recommendations": ["b"], "questions": ["c"],
    "language": "en",
}


# ---------------------------------------------------------------- helpers
def _png():
    return (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "map.png")


def _client_with_session():
    c = app.test_client()
    c.post("/register", data={"name": "A", "email": "a@example.com",
                              "password": "password123", "confirm": "password123"})
    c.post("/customers", data={"name": "ACME", "industry": "", "notes": ""})
    with app.app_context():
        cid = Customer.query.filter_by(name="ACME").first().id
    c.post(f"/customers/{cid}/sessions", data={"title": "Vision", "language": "en"})
    with app.app_context():
        sid = Session.query.filter_by(title="Vision").first().id
    return c, sid


def _upload(c, sid):
    """Upload a map with the worker thread mocked; return (map_id, worker args)."""
    with patch.object(workspace.threading, "Thread") as Thread:
        r = c.post(f"/sessions/{sid}/maps/upload",
                   data={"map_type": "vision_keywords", "image": _png()},
                   content_type="multipart/form-data")
    assert r.status_code == 302
    with app.app_context():
        mid = MapAnalysis.query.order_by(MapAnalysis.id.desc()).first().id
    return mid, Thread.call_args.kwargs["args"]


def _status(c, sid, mid):
    return c.get(f"/api/sessions/{sid}/maps/{mid}/status").get_json()


@pytest.fixture(autouse=True)
def _no_stray_workers():
    workspace._ACTIVE_ANALYSES.clear()
    yield
    workspace._ACTIVE_ANALYSES.clear()


# ---------------------------------------------------------------- registration
def test_app_routes_exist():
    endpoints = {r.endpoint for r in app.url_map.iter_rules()}
    for ep in ("workspace.map_list", "workspace.upload_map", "workspace.analyze_map_route",
               "workspace.delete_map", "workspace.map_status",
               "workspace.delete_customer", "workspace.delete_session"):
        assert ep in endpoints, f"{ep} not registered"


def test_models_initialized():
    for key in ("vision_keywords", "problem_statements", "metrics_root_cause"):
        assert key in MAP_MECHANICS
    for mechanics in MAP_MECHANICS.values():
        for field in ("name", "purpose", "mechanics", "expected_output", "evaluation_signals"):
            assert field in mechanics


# ---------------------------------------------------------------- progress
def test_upload_starts_analysis_and_reports_running():
    c, sid = _client_with_session()
    mid, _ = _upload(c, sid)
    workspace._ACTIVE_ANALYSES.add(mid)  # the mocked thread counts as alive

    s = _status(c, sid, mid)
    assert s["state"] == "running"
    assert s["step"] == "prepare"
    assert s["label"] == "Preparing the map"
    assert s["next"]  # tells the user what comes next
    assert [st["key"] for st in s["steps"]] == ["prepare", "evaluate", "validate", "describe", "done"]

    page = c.get(f"/sessions/{sid}/maps/{mid}").data.decode()
    assert "analysis_progress.js" in page
    assert "Analyzing your map" in page


def test_worker_records_steps_and_finishes():
    c, sid = _client_with_session()
    mid, args = _upload(c, sid)
    seen = []

    def fake_analyze(on_step, **_kw):
        for step in ("evaluate", "validate", "describe"):
            on_step(step)
            with app.app_context():
                seen.append(db.session.get(MapAnalysis, mid).step)
        return VALID_EVAL, "## Map"

    with patch("run.analyze_map", side_effect=fake_analyze), \
         patch("run.resolve_backend", return_value="claude_cli"):
        workspace.run_map_analysis(*args)

    assert seen == ["evaluate", "validate", "describe"]
    s = _status(c, sid, mid)
    assert s["state"] == "done" and s["step"] == "done"
    assert s["elapsed_s"] is not None
    with app.app_context():
        assert db.session.get(MapAnalysis, mid).band == "green"


def test_worker_error_is_explained_with_step():
    c, sid = _client_with_session()
    mid, args = _upload(c, sid)

    def slow(on_step, **_kw):
        on_step("evaluate")
        raise RuntimeError("Analysis failed") from subprocess.TimeoutExpired("claude", 300)

    with patch("run.analyze_map", side_effect=slow), \
         patch("run.resolve_backend", return_value="claude_cli"):
        workspace.run_map_analysis(*args)

    s = _status(c, sid, mid)
    assert s["state"] == "error"
    assert s["error"]["title"] == "The AI took too long to respond"
    assert s["error"]["where"] == "Reading & scoring the map"
    assert "Retry" in s["error"]["fix"]
    page = c.get(f"/sessions/{sid}/maps/{mid}").data.decode()
    assert "Retry analysis" in page


def test_no_backend_is_an_error_not_fake_results():
    c, sid = _client_with_session()
    mid, args = _upload(c, sid)
    with patch("run.resolve_backend", return_value="dry_run"):
        workspace.run_map_analysis(*args)
    s = _status(c, sid, mid)
    assert s["state"] == "error"
    assert s["error"]["title"] == "No AI engine available"
    with app.app_context():
        assert db.session.get(MapAnalysis, mid).band is None


def test_orphaned_running_map_is_reported_interrupted():
    """App restarted mid-analysis: row says running but no worker exists."""
    c, sid = _client_with_session()
    mid, _ = _upload(c, sid)  # thread mocked and not marked active → orphan
    workspace._ACTIVE_ANALYSES.discard(mid)
    s = _status(c, sid, mid)
    assert s["state"] == "error"
    assert s["error"]["title"] == "The analysis was interrupted"


def test_cannot_start_twice():
    c, sid = _client_with_session()
    mid, _ = _upload(c, sid)
    assert mid in workspace._ACTIVE_ANALYSES
    with patch.object(workspace.threading, "Thread") as Thread:
        r = c.post(f"/sessions/{sid}/maps/{mid}/analyze", follow_redirects=True)
    assert not Thread.called
    assert b"already being analysed" in r.data


# ---------------------------------------------------------------- error translation
@pytest.mark.parametrize("exc, title", [
    (FileNotFoundError(2, "The system cannot find the file specified"), "Claude CLI not found"),
    (RuntimeError("claude CLI exited 1: Invalid API key · Please run /login"), "Claude CLI is not signed in"),
    (RuntimeError("claude CLI exited 1: 429 rate limit"), "Claude is busy or your usage limit was reached"),
    (ValueError("No JSON object found in model response."), "The AI couldn't produce an evaluation"),
    (ValueError("Image not found: x.png"), "The map photo is missing"),
    (NoBackendError("none"), "No AI engine available"),
    (KeyError("boom"), "Something went wrong"),
])
def test_explain_error(exc, title):
    wrapped = RuntimeError("Analysis failed")
    wrapped.__cause__ = exc
    e = explain_error(wrapped, "evaluate")
    assert e["title"] == title
    assert e["where"] == "Reading & scoring the map"
    assert e["fix"]
