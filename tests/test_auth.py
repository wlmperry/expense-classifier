"""Tests for user accounts and login sessions (app/auth.py, /auth/* routes).

Most tests use unauthenticated_client (tests/conftest.py), which sends no
Authorization header, and log in through the real endpoints.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import User, UserSession
from tests.conftest import TEST_USER_PASSWORD

NEW_ACCOUNT = {"email": "new-user@example.com", "password": "a-long-password"}


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Sign-up ---


def test_register_creates_an_account_and_logs_it_in(unauthenticated_client):
    response = unauthenticated_client.post("/auth/register", json=NEW_ACCOUNT)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new-user@example.com"
    me = unauthenticated_client.get("/auth/me", headers=auth_header(body["token"]))
    assert me.status_code == 200
    assert me.json() == body["user"]


def test_register_stores_only_a_password_hash(unauthenticated_client, db_session):
    unauthenticated_client.post("/auth/register", json=NEW_ACCOUNT)

    user = db_session.execute(
        select(User).where(User.email == "new-user@example.com")
    ).scalar_one()
    assert NEW_ACCOUNT["password"] not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")


def test_register_trims_and_lowercases_the_email(unauthenticated_client):
    response = unauthenticated_client.post(
        "/auth/register", json={**NEW_ACCOUNT, "email": "  New-User@Example.COM "}
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "new-user@example.com"


def test_register_rejects_an_email_that_already_has_an_account(unauthenticated_client, user):
    response = unauthenticated_client.post(
        "/auth/register", json={**NEW_ACCOUNT, "email": user.email.upper()}
    )

    assert response.status_code == 409


def test_register_rejects_a_password_shorter_than_8_characters(unauthenticated_client):
    response = unauthenticated_client.post(
        "/auth/register", json={**NEW_ACCOUNT, "password": "1234567"}
    )

    assert response.status_code == 422


def test_register_rejects_an_invalid_email(unauthenticated_client):
    for email in ["", "no-at-sign.com", "two@@example.com", "spaces in@example.com"]:
        response = unauthenticated_client.post(
            "/auth/register", json={**NEW_ACCOUNT, "email": email}
        )
        assert response.status_code == 422, email


# --- Login ---


def test_login_with_the_right_password_returns_a_working_token(unauthenticated_client, user):
    response = unauthenticated_client.post(
        "/auth/login", json={"email": user.email, "password": TEST_USER_PASSWORD}
    )

    assert response.status_code == 200
    token = response.json()["token"]
    me = unauthenticated_client.get("/auth/me", headers=auth_header(token))
    assert me.json() == {"id": user.id, "email": user.email}


def test_login_ignores_email_capitalization(unauthenticated_client, user):
    response = unauthenticated_client.post(
        "/auth/login", json={"email": user.email.upper(), "password": TEST_USER_PASSWORD}
    )

    assert response.status_code == 200


def test_login_with_a_wrong_password_or_unknown_email_gets_the_same_401(
    unauthenticated_client, user
):
    wrong_password = unauthenticated_client.post(
        "/auth/login", json={"email": user.email, "password": "not-the-password"}
    )
    unknown_email = unauthenticated_client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": TEST_USER_PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_session_tokens_are_stored_only_as_hashes(unauthenticated_client, db_session, user):
    token = unauthenticated_client.post(
        "/auth/login", json={"email": user.email, "password": TEST_USER_PASSWORD}
    ).json()["token"]

    stored = db_session.execute(select(UserSession.token_hash)).scalars().all()
    assert token not in stored


# --- Sessions ---


def test_protected_routes_reject_a_missing_token(unauthenticated_client):
    response = unauthenticated_client.get("/expenses")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_protected_routes_reject_an_unknown_token(unauthenticated_client):
    response = unauthenticated_client.get("/expenses", headers=auth_header("made-up-token"))

    assert response.status_code == 401


def test_an_expired_session_is_rejected(client, db_session):
    for session in db_session.execute(select(UserSession)).scalars():
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()

    response = client.get("/auth/me")

    assert response.status_code == 401


def test_logout_ends_only_the_current_session(unauthenticated_client, user):
    def log_in() -> str:
        return unauthenticated_client.post(
            "/auth/login", json={"email": user.email, "password": TEST_USER_PASSWORD}
        ).json()["token"]

    laptop, phone = log_in(), log_in()

    response = unauthenticated_client.post("/auth/logout", headers=auth_header(laptop))

    assert response.status_code == 204
    assert unauthenticated_client.get("/auth/me", headers=auth_header(laptop)).status_code == 401
    assert unauthenticated_client.get("/auth/me", headers=auth_header(phone)).status_code == 200


def test_read_root_requires_no_token(unauthenticated_client):
    response = unauthenticated_client.get("/")

    assert response.status_code == 200
