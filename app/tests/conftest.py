"""Shared test setup: point the app at a temp SQLite DB and reset it per test.

Env vars are set BEFORE importing server so the app configures itself against the
throwaway database and a test secret (never the real app/engage2win.db)."""
import os
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

_TEST_DB = Path(tempfile.gettempdir()) / "engage2win_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest  # noqa: E402
import server  # noqa: E402  (configures Flask app + db against the temp DB)
from models import db  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """Give every test a clean database."""
    with server.app.app_context():
        db.drop_all()
        db.create_all()
    yield
