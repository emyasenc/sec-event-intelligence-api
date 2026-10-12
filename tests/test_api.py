"""API tests for SEC Event Intelligence API."""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data


def test_health_check():
    """Test health endpoint returns status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]


def test_pricing_endpoint():
    """Test pricing endpoint returns all tiers."""
    response = client.get("/api/v1/pricing")
    assert response.status_code == 200
    data = response.json()
    assert "tiers" in data
    assert len(data["tiers"]) == 4
    assert "free" in data["tiers"]
    assert "pro" in data["tiers"]
    assert "ultra" in data["tiers"]
    assert "mega" in data["tiers"]


def test_event_types_endpoint():
    """Test event types endpoint returns all types."""
    response = client.get("/api/v1/events/types")
    assert response.status_code == 200
    data = response.json()
    assert "event_types" in data
    assert len(data["event_types"]) >= 8
