"""
Tests for FeedbackService – feedback.py
Covers: create_feedback, list_feedback, update_feedback
"""


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


def test_create_feedback_no_booking(client_no_booking):
    c, _, event = client_no_booking
    resp = c.post("/api/feedback", json={"event_id": event.id, "message": "Should fail"})
    assert resp.status_code == 403


def test_create_feedback_event_not_found(client, db):
    from unittest.mock import patch, MagicMock

    c, _, _ = client

    def _not_found(*args, **kwargs):
        m = MagicMock()
        m.status_code = 404
        return m

    with patch("utility.get", side_effect=_not_found):
        resp = c.post("/api/feedback", json={"event_id": 9999, "message": "No event"})
    assert resp.status_code == 404


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


def test_update_feedback_wrong_user(client, client_no_booking, db):
    import models, auth
    from datetime import datetime

    c, _, event = client

    # create feedback as user 1
    feedback_id = c.post("/api/feedback", json={"event_id": event.id, "message": "Mine"}).json()["id"]

    # try to update it as user 2 (who has no booking, but that doesn't matter here —
    # the ownership check happens before the booking check in update)
    c2, _, _ = client_no_booking
    resp = c2.patch(f"/api/feedback/{feedback_id}", json={"message": "Not mine"})
    assert resp.status_code == 404


def test_health(client):
    c, _, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "FeedbackService"
