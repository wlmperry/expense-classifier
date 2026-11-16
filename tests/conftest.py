"""Fixtures for PostgreSQL persistence tests.

Persistence tests run against a dedicated TEST_DATABASE_URL database, never
against the application's own DATABASE_URL, so they cannot depend on or
disturb a developer's normal expense_classifier_dev contents. If
TEST_DATABASE_URL is not configured, tests that need it are skipped rather
than silently falling back to DATABASE_URL.
"""

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  # registers every model on Base.metadata
from app.auth import create_session, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User

load_dotenv()

TEST_USER_PASSWORD = "correct-horse-battery"
# Hashed once per test run instead of once per test: Argon2id is slow on
# purpose, and almost every test needs a user.
_TEST_USER_PASSWORD_HASH = hash_password(TEST_USER_PASSWORD)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# The dedicated test database schema is dropped and recreated on every test
# session (see test_engine below). This name check is a fail-safe so a
# misconfigured TEST_DATABASE_URL can never point that at expense_classifier_dev
# or any other database by accident.
EXPECTED_TEST_DATABASE_NAME = "expense_classifier_test"


@pytest.fixture(scope="session")
def test_engine():
    if not TEST_DATABASE_URL:
        pytest.skip(
            "TEST_DATABASE_URL is not set; see docs/development.md to configure "
            "the dedicated expense_classifier_test database."
        )

    engine = create_engine(TEST_DATABASE_URL)

    try:
        with engine.connect() as connection:
            actual_database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar()

        if actual_database_name != EXPECTED_TEST_DATABASE_NAME:
            pytest.fail(
                f"TEST_DATABASE_URL connects to database {actual_database_name!r}, "
                f"not the expected dedicated test database "
                f"{EXPECTED_TEST_DATABASE_NAME!r}. Refusing to drop/create tables "
                "on an unexpected database."
            )

        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """A session bound to a rolled-back transaction, so no test row persists."""
    connection = test_engine.connect()
    transaction = connection.begin()
    # create_savepoint: the session rolls back to a SAVEPOINT on a failed flush
    # (e.g. a rejected CHECK constraint) instead of ending the outer `transaction`,
    # so it stays valid for the explicit rollback below regardless of test outcome.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def make_user(db_session, email: str) -> User:
    """Insert a user whose password is TEST_USER_PASSWORD."""
    user = User(email=email, password_hash=_TEST_USER_PASSWORD_HASH)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def user(db_session):
    """The user `client` is logged in as."""
    return make_user(db_session, "test-user@example.com")


@pytest.fixture
def other_user(db_session):
    """A second user, for checking that users can't see each other's data."""
    return make_user(db_session, "other-user@example.com")


@pytest.fixture
def unauthenticated_client(db_session):
    """A TestClient whose requests run inside `db_session`'s rolled-back
    transaction, instead of the app's real DATABASE_URL session. Sends no
    Authorization header, so protected routes return 401."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(unauthenticated_client, db_session, user):
    """Like unauthenticated_client, but logged in as `user` through a real
    session, so every request goes through the real auth dependency."""
    # A separate TestClient, so a test that uses both fixtures still has
    # one client without the header.
    token = create_session(db_session, user)
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})
