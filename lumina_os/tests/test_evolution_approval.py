"""Evolution approval API tests (post-Streamlit)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lumina_os.backend.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_evolution_tree_endpoint_returns_schema(client: TestClient) -> None:
    response = client.get("/api/evolution/tree?depth=5")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "1.0"
    assert "nodes" in body
    assert "edges" in body
    assert "pending_mutations" in body


def test_evolution_proposals_returns_list(client: TestClient) -> None:
    response = client.get("/api/evolution/proposals")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
