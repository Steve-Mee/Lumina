"""Approval Twin training API tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lumina_os.backend.app import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Isolate twin state under tmp so tests never touch repo state/
    monkeypatch.setenv("LUMINA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("APPROVAL_TWIN_MODEL_PATH", str(tmp_path / "approval_twin_model.json"))
    monkeypatch.setenv("TWIN_DECISIONS_PATH", str(tmp_path / "monitoring_twin_decisions.jsonl"))
    monkeypatch.setenv("TWIN_TRAINING_PATH", str(tmp_path / "monitoring_twin_training.jsonl"))
    monkeypatch.setenv("STEVE_VALUES_SQLITE", str(tmp_path / "steve_values_registry.sqlite3"))
    monkeypatch.setenv("STEVE_VALUES_JSONL", str(tmp_path / "steve_values_registry.jsonl"))
    # Ensure SIM mode does not force API key for reads/writes in unit tests
    monkeypatch.delenv("LUMINA_MODE", raising=False)
    monkeypatch.delenv("TRADE_MODE", raising=False)
    monkeypatch.setenv("LUMINA_RUNTIME_MODE", "sim")

    # Re-bind module-level paths used by twin_endpoints (set at import time)
    import backend.twin_endpoints as te

    te._STATE = tmp_path
    te._MODEL_PATH = tmp_path / "approval_twin_model.json"
    te._DECISIONS_PATH = tmp_path / "monitoring_twin_decisions.jsonl"
    te._TRAINING_PATH = tmp_path / "monitoring_twin_training.jsonl"
    te._REGISTRY_SQLITE = tmp_path / "steve_values_registry.sqlite3"
    te._REGISTRY_JSONL = tmp_path / "steve_values_registry.jsonl"

    # Seed one twin decision for the review queue
    te._DECISIONS_PATH.write_text(
        json.dumps(
            {
                "dna_hash": "deadbeefcafebabe",
                "score": 0.82,
                "recommendation": True,
                "explanation": "clean risk guard",
                "risk_flags": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return TestClient(app)


def test_twin_metrics(client: TestClient) -> None:
    r = client.get("/api/twin/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body.get("local_only") is True
    assert "threshold" in body


def test_twin_review_queue(client: TestClient) -> None:
    r = client.get("/api/twin/review-queue?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert body["local_only"] is True
    assert body["items"][0]["dna_hash"] == "deadbeefcafebabe"
    assert body["items"][0].get("stakes") in {"high", "routine"}


def test_twin_review_queue_hides_labeled(client: TestClient) -> None:
    client.post(
        "/api/twin/label",
        json={
            "decision": "approve",
            "dna_hash": "deadbeefcafebabe",
            "train_now": False,
        },
    )
    hidden = client.get("/api/twin/review-queue?limit=10&include_labeled=false")
    assert hidden.status_code == 200
    assert all(i.get("dna_hash") != "deadbeefcafebabe" for i in hidden.json()["items"])
    shown = client.get("/api/twin/review-queue?limit=10&include_labeled=true")
    assert shown.status_code == 200
    assert any(i.get("dna_hash") == "deadbeefcafebabe" for i in shown.json()["items"])


def test_twin_label_approve_and_list(client: TestClient) -> None:
    r = client.post(
        "/api/twin/label",
        json={
            "decision": "approve",
            "dna_hash": "deadbeefcafebabe",
            "twin_score": 0.82,
            "twin_recommendation": True,
            "explanation": "clean risk guard",
            "risk_flags": [],
            "train_now": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recorded"] is True
    assert body["label"] == "APPROVE"
    assert body["rlhf"] is not None
    assert body.get("local_only") is True
    assert body.get("audit") is not None

    labels = client.get("/api/twin/labels?limit=20")
    assert labels.status_code == 200
    payload = labels.json()
    assert payload["count"] >= 1
    assert payload["local_only"] is True


def test_twin_label_modify(client: TestClient) -> None:
    r = client.post(
        "/api/twin/label",
        json={
            "decision": "modify",
            "dna_hash": "modhash001",
            "notes": "half size only",
            "train_now": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["label"].startswith("MODIFY")


def test_twin_label_missing_dna(client: TestClient) -> None:
    r = client.post(
        "/api/twin/label",
        json={"decision": "approve", "dna_hash": "  "},
    )
    assert r.status_code == 400


def test_twin_train(client: TestClient) -> None:
    client.post(
        "/api/twin/label",
        json={
            "decision": "reject",
            "dna_hash": "veto1",
            "train_now": False,
        },
    )
    r = client.post("/api/twin/train", json={"limit": 50})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "result" in body
    assert "metrics" in body


def test_twin_gym_session_and_answer(client: TestClient) -> None:
    r = client.post(
        "/api/twin/gym/session",
        json={"count": 3, "prefer_historical": False},
    )
    assert r.status_code == 200, r.text
    session = r.json()
    assert session["count"] == 3
    assert session["practice_only"] is True
    assert session["promotes_dna"] is False
    prop = session["proposals"][0]

    ans = client.post(
        "/api/twin/gym/answer",
        json={
            "decision": "approve",
            "dna_hash": prop["dna_hash"],
            "summary": prop["summary"],
            "estimated_confidence": prop["estimated_confidence"],
            "session_id": session["session_id"],
            "train_now": True,
        },
    )
    assert ans.status_code == 200, ans.text
    body = ans.json()
    assert body["recorded"] is True
    assert body["practice_only"] is True


def test_twin_gym_complete(client: TestClient) -> None:
    r = client.post(
        "/api/twin/gym/session",
        json={"count": 3, "prefer_historical": False},
    )
    assert r.status_code == 200
    session = r.json()
    answers = [
        {
            "decision": "reject",
            "dna_hash": p["dna_hash"],
            "summary": p["summary"],
            "estimated_confidence": p["estimated_confidence"],
        }
        for p in session["proposals"]
    ]
    done = client.post(
        "/api/twin/gym/complete",
        json={
            "answers": answers,
            "session_id": session["session_id"],
            "train_now": True,
        },
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["recorded_count"] == 3
    assert body["rlhf"] is not None
    assert body["local_only"] is True
