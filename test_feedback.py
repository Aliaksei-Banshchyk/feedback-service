"""
Tests for FeedbackService – feedback.py
Covers: create_feedback, list_feedback, update_feedback
"""
from unittest.mock import patch, MagicMock


def _not_found(*a, **kw):
    m = MagicMock()
    m.status_code = 404
    return m


# ── create_feedback ───────────────────────────────────────────────────────────

def test_create_feedback_success(client):
    c, user, event = client
    resp = c.post("/api/feedback", json={"event_id": event.id, "message": "Great event!"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["event_id"] == event.id
    assert data["user_id"] == user.id
    assert data["message"] == "Great event!"
    assert "id" in data
    assert "created_at" in data


def test_create_feedback_no_booking(client, db):
    """Posting feedback for an event the current user never booked — expects 403."""
    import models
    from datetime import datetime

    c, _, _ = client

    # Create a second event that the test_user has no booking for
    unbooked_event = models.Event(
        event_date=datetime(2025, 10, 1, 10, 0), place="Other Venue", description=None
    )
    db.add(unbooked_event)
    db.commit()

    resp = c.post("/api/feedback", json={"event_id": unbooked_event.id, "message": "Should fail"})
    assert resp.status_code == 403


def test_create_feedback_event_not_found(client):
    c, _, _ = client
    with patch("utility.get", side_effect=_not_found):
        resp = c.post("/api/feedback", json={"event_id": 9999, "message": "No event"})
    assert resp.status_code == 404


# ── list_feedback ─────────────────────────────────────────────────────────────

def test_list_feedback_for_event(client):
    c, _, event = client
    c.post("/api/feedback", json={"event_id": event.id, "message": "First!"})
    resp = c.get(f"/api/feedback/event/{event.id}")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert all(f["event_id"] == event.id for f in items)


def test_list_feedback_event_not_found(client):
    c, _, _ = client
    resp = c.get("/api/feedback/event/99999")
    assert resp.status_code == 404


# ── update_feedback ───────────────────────────────────────────────────────────

def test_update_feedback_success(client):
    c, _, event = client
    feedback_id = c.post("/api/feedback", json={"event_id": event.id, "message": "Original"}).json()["id"]
    resp = c.patch(f"/api/feedback/{feedback_id}", json={"message": "Updated message"})
    assert resp.status_code == 200
    assert resp.json()["message"] == "Updated message"


def test_update_feedback_not_found(client):
    c, _, _ = client
    resp = c.patch("/api/feedback/99999", json={"message": "Ghost"})
    assert resp.status_code == 404


# ── health ────────────────────────────────────────────────────────────────────

def test_health(client):
    c, _, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "FeedbackService"