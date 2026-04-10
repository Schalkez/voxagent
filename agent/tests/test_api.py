"""Tests for the FastAPI management server."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from api.server import app

# ── Auth token for tests ──
_TEST_TOKEN = "test-api-token-for-tests"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app with lifespan context.

    Sets a known auth token via env var so the lifespan initializes
    with the same token that the test client uses.
    """
    old = os.environ.get("VOXAGENT_API_TOKEN")
    os.environ["VOXAGENT_API_TOKEN"] = _TEST_TOKEN
    try:
        with TestClient(app) as client:
            client.headers["Authorization"] = f"Bearer {_TEST_TOKEN}"
            yield client
    finally:
        if old is None:
            os.environ.pop("VOXAGENT_API_TOKEN", None)
        else:
            os.environ["VOXAGENT_API_TOKEN"] = old


class TestProviderEndpoints:
    """Test provider management endpoints."""

    def test_list_providers(self, client: TestClient) -> None:
        """GET /api/providers should return provider list."""
        response = client.get("/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_provider_has_required_fields(self, client: TestClient) -> None:
        """Each provider should have id, name, and status."""
        response = client.get("/api/providers")
        data = response.json()
        for provider in data:
            assert "id" in provider
            assert "name" in provider
            assert "status" in provider


class TestRoutingEndpoints:
    """Test routing configuration endpoints."""

    def test_get_routing(self, client: TestClient) -> None:
        """GET /api/routing should return routing config."""
        response = client.get("/api/routing")
        assert response.status_code == 200
        data = response.json()
        assert "preset" in data
        assert "tiers" in data


class TestSkillsEndpoints:
    """Test skills management endpoints."""

    def test_list_skills(self, client: TestClient) -> None:
        """GET /api/skills should return skills list."""
        response = client.get("/api/skills")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestSettingsEndpoints:
    """Test settings endpoints."""

    def test_get_settings(self, client: TestClient) -> None:
        """GET /api/settings should return current settings."""
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
