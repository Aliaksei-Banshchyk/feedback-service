"""
test_feedback.py – FeedbackService
Place at the ROOT of the feedback-service repo.
Run with: pytest test_feedback.py -v
"""
import pytest


FEEDBACK_PAYLOAD = {"event_id": 1, "message": "Great event!"}


# ── /health ───────────────────────────────────────────────────────────────────

def test_health(client):
    c, _, __ = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── POST /api/feedback ────────────────────────────────────────────────────────

def test_create_feedback_success(client):
    c, _, __ = client
    r = c.post("/api/feedback", json=FEEDBACK_PAYLOAD)
    assert r.status_code == 201
    data = r.json()
    assert data["message"] == "Great event!"
    assert data["event_id"] == 1
    assert "id" in data
    assert "created_at" in data


def test_create_feedback_event_not_found(client, monkeypatch):
    c, _, __ = client
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    monkeypatch.setattr("utility.get", lambda *a, **kw: mock_resp)
    r = c.post("/api/feedback", json={"event_id": 99999, "message": "Test"})
    assert r.status_code == 404


def test_create_feedback_no_booking(client_no_booking):
    c, _, event = client_no_booking
    r = c.post("/api/feedback", json={"event_id": event.id, "message": "Test"})
    assert r.status_code == 403


def test_create_feedback_missing_message(client):
    c, _, __ = client
    r = c.post("/api/feedback", json={"event_id": 1})
    assert r.status_code == 422


# ── GET /api/feedback/event/{event_id} ────────────────────────────────────────

def test_list_feedback_success(client):
    c, _, test_event = client
    c.post("/api/feedback", json={"event_id": test_event.id, "message": "msg1"})
    c.post("/api/feedback", json={"event_id": test_event.id, "message": "msg2"})
    r = c.get(f"/api/feedback/event/{test_event.id}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 2
    assert all(i["event_id"] == test_event.id for i in items)


def test_list_feedback_event_not_found(client):
    c, _, __ = client
    r = c.get("/api/feedback/event/99999")
    assert r.status_code == 404


def test_list_feedback_empty(client, db):
    from datetime import datetime
    import models
    c, _, __ = client
    empty_event = models.Event(
        id=50, event_date=datetime(2025, 11, 1, 10, 0),
        place="Empty Venue", description=None,
    )
    db.add(empty_event)
    db.commit()
    r = c.get("/api/feedback/event/50")
    assert r.status_code == 200
    assert r.json() == []


# ── PATCH /api/feedback/{id} ──────────────────────────────────────────────────

def test_update_feedback_success(client):
    c, _, test_event = client
    created = c.post("/api/feedback", json={
        "event_id": test_event.id, "message": "Original"
    })
    feedback_id = created.json()["id"]
    r = c.patch(f"/api/feedback/{feedback_id}", json={"message": "Updated"})
    assert r.status_code == 200
    assert r.json()["message"] == "Updated"


def test_update_feedback_not_found(client):
    c, _, __ = client
    r = c.patch("/api/feedback/99999", json={"message": "x"})
    assert r.status_code == 404


def test_update_feedback_empty_patch(client):
    c, _, test_event = client
    created = c.post("/api/feedback", json={
        "event_id": test_event.id, "message": "Keep this"
    })
    feedback_id = created.json()["id"]
    r = c.patch(f"/api/feedback/{feedback_id}", json={})
    assert r.status_code == 200
    assert r.json()["message"] == "Keep this"
