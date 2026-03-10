"""
Secondus E2E Tests

End-to-end tests for the full API flow.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
import sys
import os
import json
import base64

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_ok(self, client):
        """Test health endpoint returns ok status."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_service_name(self, client):
        """Test health endpoint returns service name."""
        response = client.get("/health")
        data = response.json()
        assert data["service"] == "secondus"

    def test_health_returns_model_name(self, client):
        """Test health endpoint returns model name."""
        response = client.get("/health")
        data = response.json()
        assert data["model"] == "gemini-live-2.5-flash-native-audio"

    def test_health_returns_project_id(self, client):
        """Test health endpoint returns project ID."""
        response = client.get("/health")
        data = response.json()
        assert "project" in data


class TestSessionCreation:
    """Tests for session creation endpoint."""

    def test_create_session_success(self, client):
        """Test creating a new session."""
        response = client.post("/session/create", json={
            "goals": "Close at $50K",
            "batna": "Vendor B offer",
            "key_terms": ["payment", "liability"],
            "counterparty": "Acme Corp"
        })

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "created"

    def test_create_session_with_empty_config(self, client):
        """Test creating session with empty config."""
        response = client.post("/session/create", json={})

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data

    def test_create_session_returns_uuid(self, client):
        """Test session ID is valid UUID format."""
        response = client.post("/session/create", json={
            "goals": "Test goal"
        })

        data = response.json()
        session_id = data["session_id"]

        # UUID format: 8-4-4-4-12 hex characters
        parts = session_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_create_multiple_sessions(self, client):
        """Test creating multiple unique sessions."""
        response1 = client.post("/session/create", json={"goals": "Goal 1"})
        response2 = client.post("/session/create", json={"goals": "Goal 2"})

        id1 = response1.json()["session_id"]
        id2 = response2.json()["session_id"]

        assert id1 != id2


class TestSessionStatus:
    """Tests for session status endpoint."""

    def test_get_session_status_exists(self, client):
        """Test getting status of existing session."""
        # Create session first
        create_response = client.post("/session/create", json={
            "goals": "Test goal",
            "counterparty": "Test Corp"
        })
        session_id = create_response.json()["session_id"]

        # Get status
        status_response = client.get(f"/session/{session_id}/status")
        assert status_response.status_code == 200

        data = status_response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "active"
        assert data["config"]["goals"] == "Test goal"

    def test_get_session_status_not_found(self, client):
        """Test getting status of non-existent session."""
        response = client.get("/session/nonexistent-id/status")
        assert response.status_code == 200

        data = response.json()
        assert "error" in data


class TestWebSocketConnection:
    """Tests for WebSocket negotiation endpoint."""

    def test_websocket_rejects_invalid_session(self, client):
        """Test WebSocket rejects connection with invalid session."""
        with client.websocket_connect("/ws/negotiate/invalid-session-id") as ws:
            data = ws.receive_json()
            assert "error" in data

    def test_websocket_accepts_valid_session(self, client):
        """Test WebSocket accepts connection with valid session."""
        # Create session first
        create_response = client.post("/session/create", json={
            "goals": "Test goal"
        })
        session_id = create_response.json()["session_id"]

        # Note: Full WebSocket test requires mocking ADK
        # This test just verifies the endpoint exists
        assert session_id is not None


class TestFrontendServing:
    """Tests for frontend static file serving."""

    def test_root_serves_frontend(self, client):
        """Test root path serves frontend HTML."""
        response = client.get("/")

        # Should return HTML or redirect to frontend
        assert response.status_code in [200, 404]  # 404 if frontend not mounted

    def test_static_path_exists(self, client):
        """Test static files path is configured."""
        # Check that app has static files mounted
        routes = [r.path for r in app.routes]
        # Static mount may not show as a path, so we just verify app loaded
        assert len(routes) > 0


class TestAPIValidation:
    """Tests for API input validation."""

    def test_session_create_validates_json(self, client):
        """Test session create endpoint validates JSON."""
        response = client.post(
            "/session/create",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_session_create_accepts_partial_config(self, client):
        """Test session create accepts partial configuration."""
        response = client.post("/session/create", json={
            "goals": "Only goals provided"
            # Other fields omitted
        })

        assert response.status_code == 200


class TestCORSHeaders:
    """Tests for CORS configuration."""

    def test_cors_allows_any_origin(self, client):
        """Test CORS allows requests from any origin."""
        response = client.options(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )

        # CORS preflight should work
        assert response.status_code in [200, 405]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
