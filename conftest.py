"""
conftest.py – FeedbackService
Place at the ROOT of the feedback-service repo alongside feedback.py.

Mocks:
  - utility.get  (EventService HTTP calls)
  - feedback_message_broker.start_receiver / subscribe / publish
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock
from datetime import datetime

SQLITE_URL = "sqlite:///./test.db"

with patch.dict(os.environ, {
    "DB_USERNAME": "test", "DB_PASSWORD": "test",
    "DB_SERVER": "localhost", "DB_DATABASE": "test",
}):
    import database
    import models

database.engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
database.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=database.engine
)

for table in models.Base.metadata.tables.values():
    table.schema = None

import auth
from database import get_db
from auth import get_current_user


def _mock_event_found(*args, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _mock_event_not_found(*args, **kwargs):
    resp = MagicMock()
    resp.status_code = 404
    return resp


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    models.Base.metadata.create_all(bind=database.engine)
    yield
    models.Base.metadata.drop_all(bind=database.engine)
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture()
def db():
    connection = database.engine.connect()
    transaction = connection.begin()
    session = database.SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    test_user = models.User(
        id=1, login="testuser",
        password=auth.hash_password("password123"),
        name="Test User",
    )
    test_event = models.Event(
        id=1, event_date=datetime(2025, 9, 1, 10, 0),
        place="Test Venue", description="Test event",
    )
    # Create a booking so feedback creation passes the booking check
    db.add(test_user)
    db.add(test_event)
    db.flush()
    test_booking = models.Booking(
        id=1, user_id=test_user.id, event_id=test_event.id,
    )
    db.add(test_booking)
    db.commit()

    from main import app
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with patch("utility.get", side_effect=_mock_event_found), \
         patch("feedback_message_broker.start_receiver", return_value=None), \
         patch("feedback_message_broker.subscribe", return_value=None):
        with TestClient(app) as c:
            yield c, test_user, test_event

    app.dependency_overrides.clear()


@pytest.fixture()
def client_no_booking(db):
    """Client where user has no booking for the event — feedback should be 403."""
    from fastapi.testclient import TestClient

    user2 = models.User(
        id=2, login="nobooking",
        password=auth.hash_password("password123"),
        name="No Booking User",
    )
    event2 = models.Event(
        id=2, event_date=datetime(2025, 10, 1, 10, 0),
        place="Other Venue", description=None,
    )
    db.add(user2)
    db.add(event2)
    db.commit()

    from main import app
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user2

    with patch("utility.get", side_effect=_mock_event_found), \
         patch("feedback_message_broker.start_receiver", return_value=None), \
         patch("feedback_message_broker.subscribe", return_value=None):
        with TestClient(app) as c:
            yield c, user2, event2

    app.dependency_overrides.clear()
