"""Shared fixtures of the backend tests.

pytest loads this file before the tests and gives each test the fixtures it
names as arguments.

- The tests use a database of their own, <MYSQL_DATABASE>_test, on the same
  MySQL server as the app. It is created if it does not exist and its tables
  are rebuilt with the Alembic migrations once per test run.
- Every test runs inside one transaction that is rolled back at the end, so
  nothing a test writes is left behind for the next one.
- Gemini and ffmpeg are never called: the functions that call them are
  replaced with mocks.
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, create_engine, pool, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
# The same .env as the app reads (see app/config.py). app.config cannot be
# imported for this yet: it reads the settings the moment it is imported
ENV_FILE = BACKEND_DIR.parent / ".env"


class RootDatabaseSettings(BaseSettings):
    """The values the tests need to create the test database as root."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    mysql_database: str
    mysql_user: str
    mysql_root_password: str
    db_host: str = "localhost"
    db_port: int = 3306


root_settings = RootDatabaseSettings()
TEST_DATABASE = f"{root_settings.mysql_database}_test"

# Environment variables win over .env, so the app imported below connects to
# the test database and never sees the real Gemini key. This must run before
# the first "from app ..." import.
os.environ["MYSQL_DATABASE"] = TEST_DATABASE
os.environ["GEMINI_API_KEY"] = "test-key-not-used"

from alembic.command import downgrade, upgrade
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import settings
from app.database import engine, get_db
from app.main import app
from app.models import ActionItem, Meeting, MeetingStatus
from app.routers import meetings as meetings_router
from app.services import processing


def _create_test_database() -> None:
    """Create the test database and give the app's user access to it.

    The app's user may only use its own database, so this runs as root.
    """
    root_url = URL.create(
        "mysql+pymysql",
        username="root",
        password=root_settings.mysql_root_password,
        host=root_settings.db_host,
        port=root_settings.db_port,
    )
    root_engine = create_engine(root_url, poolclass=pool.NullPool)
    with root_engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{TEST_DATABASE}`"))
        connection.execute(
            text(
                f"GRANT ALL PRIVILEGES ON `{TEST_DATABASE}`.* "
                f"TO '{root_settings.mysql_user}'@'%'"
            )
        )
    root_engine.dispose()


def _migrate_test_database() -> None:
    """Drop all tables and build them again with the Alembic migrations."""
    # Built without alembic.ini on purpose: alembic/env.py sets up logging from
    # that file, which would switch off the loggers of the app during the tests
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    downgrade(config, "base")
    upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Runs once, before the first test."""
    _create_test_database()
    _migrate_test_database()
    yield
    engine.dispose()


@pytest.fixture
def connection():
    """One connection with an open transaction, rolled back after the test."""
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


@pytest.fixture
def session_factory(connection):
    """Makes sessions that work inside the transaction of the test.

    create_savepoint: commit() in the app's code only ends a savepoint, so the
    data stays inside the outer transaction, which is rolled back at the end.
    """
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture
def db(session_factory):
    """A session for the test itself: to prepare data and check the result."""
    with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def isolated_app(session_factory, monkeypatch, tmp_path):
    """Point the app at the test transaction and at a temporary upload folder.

    monkeypatch undoes every change it made when the test ends.
    """

    def get_test_db():
        with session_factory() as session:
            yield session

    # The endpoints get their session through get_db; process_meeting opens
    # its own with SessionLocal
    app.dependency_overrides[get_db] = get_test_db
    monkeypatch.setattr(processing, "SessionLocal", session_factory)
    # tmp_path: an empty folder pytest creates for this one test
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def ai_mocks(monkeypatch):
    """Replace the functions that call ffmpeg and Gemini, in every test.

    They are replaced in app.services.processing, because that is the module
    that looks them up by name when process_meeting runs. A test sets what
    they return (return_value) or raise (side_effect).
    """
    mocks = SimpleNamespace(
        extract_audio=Mock(),
        transcribe_audio=Mock(),
        analyze_transcript=Mock(),
    )
    for name, mock in vars(mocks).items():
        monkeypatch.setattr(processing, name, mock)
    return mocks


@pytest.fixture
def process_meeting_mock(monkeypatch):
    """Replace the background processing that the upload and process
    endpoints start, so an API test only checks the endpoint itself."""
    mock = Mock()
    monkeypatch.setattr(meetings_router, "process_meeting", mock)
    return mock


@pytest.fixture
def client(process_meeting_mock):
    """Sends requests to the app without starting a server.

    Created without "with", so the startup code (lifespan) does not run.
    """
    return TestClient(app)


@pytest.fixture
def make_meeting(db):
    """Return a function that stores a meeting with made-up data."""

    def _make_meeting(
        status: MeetingStatus = MeetingStatus.DONE,
        action_items: list[tuple[str | None, str]] = (),
        **fields,
    ) -> Meeting:
        fields.setdefault("original_filename", "weekly-sync.mp4")
        fields.setdefault("file_path", "1/original.mp4")
        meeting = Meeting(status=status, **fields)
        meeting.action_items = [
            ActionItem(assignee=assignee, description=description)
            for assignee, description in action_items
        ]
        db.add(meeting)
        db.commit()
        return meeting

    return _make_meeting
