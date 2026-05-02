import os
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
database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)

for table in models.Base.metadata.tables.values():
    table.schema = None

import auth
from database import get_db
from auth import get_current_user


def _event_found(*args, **kwargs):
    m = MagicMock()
    m.status_code = 200
    return m


def _event_not_found(*args, **kwargs):
    m = MagicMock()
    m.status_code = 404
    return m


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
    connection.begin()
    session = database.SessionLocal(bind=connection)
    yield session
    session.close()
    connection.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient
    from main import app

    # No hardcoded IDs — let the DB auto-assign to avoid clashes across tests
    test_user = models.User(
        login="testuser",
        password=auth.hash_password("password123"),
        name="Test User",
    )
    test_event = models.Event(
        event_date=datetime(2025, 9, 1, 10, 0),
        place="Test Venue",
        description="Test event",
    )
    db.add(test_user)
    db.add(test_event)
    db.flush()
    db.add(models.Booking(user_id=test_user.id, event_id=test_event.id))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with patch("utility.get", side_effect=_event_found), \
         patch("feedback_message_broker.start_receiver", return_value=None), \
         patch("feedback_message_broker.subscribe", return_value=None):
        with TestClient(app) as c:
            yield c, test_user, test_event

    app.dependency_overrides.clear()