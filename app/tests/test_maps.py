"""Tests for Phase 4 map analysis routes.

Note: These are basic smoke tests. Full integration tests would require
proper Flask-Login session management in the test client. For MVP, the
features have been verified to work in the browser.
"""
import pytest
from app.server import app


def test_app_routes_exist():
    """Verify that Phase 4 routes are registered in the app."""
    with app.app_context():
        # Check that map-related routes exist by looking for their endpoints
        endpoints = [str(r.endpoint) for r in app.url_map.iter_rules()]

        # Check key workspace endpoints
        assert "workspace.map_list" in endpoints, "Map list endpoint not found"
        assert "workspace.upload_map" in endpoints, "Map upload endpoint not found"
        assert "workspace.analyze_map_route" in endpoints, "Map analyze endpoint not found"
        assert "workspace.delete_map" in endpoints, "Map delete endpoint not found"


def test_models_initialized():
    """Verify that Phase 4 models are properly initialized."""
    from app.models import MapAnalysis, MAP_MECHANICS

    # Check that MapAnalysis model exists
    assert MapAnalysis is not None

    # Check that MAP_MECHANICS has the expected map types
    assert "vision_keywords" in MAP_MECHANICS
    assert "problem_statements" in MAP_MECHANICS
    assert "metrics_root_cause" in MAP_MECHANICS

    # Check structure of mechanics
    for map_type, mechanics in MAP_MECHANICS.items():
        assert "name" in mechanics
        assert "purpose" in mechanics
        assert "mechanics" in mechanics
        assert "expected_output" in mechanics
        assert "evaluation_signals" in mechanics


def test_delete_routes_registered():
    """Verify that delete routes for customers and sessions exist."""
    with app.app_context():
        endpoints = [str(r.endpoint) for r in app.url_map.iter_rules()]

        # Check delete endpoints
        assert "workspace.delete_customer" in endpoints, \
            "Customer delete endpoint not found"

        assert "workspace.delete_session" in endpoints, \
            "Session delete endpoint not found"

        assert "workspace.delete_map" in endpoints, \
            "Map delete endpoint not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
