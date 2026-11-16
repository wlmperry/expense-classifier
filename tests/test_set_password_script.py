"""Tests for scripts/set_password.py's set_password() (Issue #44).

main() only adds the prompts around it, so it isn't tested here.
"""

import pytest

from app.auth import authenticate, create_session
from scripts.set_password import SetPasswordError, set_password
from tests.conftest import TEST_USER_PASSWORD

NEW_PASSWORD = "a-brand-new-password"


def test_the_new_password_works_and_the_old_one_does_not(db_session, user):
    set_password(db_session, user.email, NEW_PASSWORD)

    assert authenticate(db_session, user.email, NEW_PASSWORD) == user
    assert authenticate(db_session, user.email, TEST_USER_PASSWORD) is None


def test_email_is_matched_regardless_of_capitalization(db_session, user):
    stored_email = set_password(db_session, f"  {user.email.upper()} ", NEW_PASSWORD)

    assert stored_email == user.email
    assert authenticate(db_session, user.email, NEW_PASSWORD) == user


def test_existing_sessions_are_ended(unauthenticated_client, db_session, user):
    token = create_session(db_session, user)

    set_password(db_session, user.email, NEW_PASSWORD)

    response = unauthenticated_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_unknown_email_is_an_error(db_session):
    with pytest.raises(SetPasswordError, match="No account"):
        set_password(db_session, "nobody@example.com", NEW_PASSWORD)


def test_a_too_short_password_is_rejected(db_session, user):
    with pytest.raises(SetPasswordError, match="password"):
        set_password(db_session, user.email, "short")

    assert authenticate(db_session, user.email, TEST_USER_PASSWORD) == user
