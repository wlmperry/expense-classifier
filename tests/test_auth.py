"""Tests for the shared bearer-token dependency (app/auth.py).

Uses unauthenticated_client (tests/conftest.py), which leaves the real
require_auth_token dependency in place -- every other test uses the plain
client fixture, which overrides it to a no-op.
"""

VALID_PAYLOAD = {
    "merchant": "DOLLAR GENERAL STORE #16600",
    "description": "S RED BULL 8.4C",
    "amount": "2.75",
    "expense_date": "2026-08-29",
}


def test_create_expense_without_token_is_rejected(unauthenticated_client):
    response = unauthenticated_client.post("/expenses", json=VALID_PAYLOAD)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_create_expense_with_wrong_token_is_rejected(unauthenticated_client):
    response = unauthenticated_client.post(
        "/expenses",
        json=VALID_PAYLOAD,
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_create_expense_with_correct_token_succeeds(unauthenticated_client):
    response = unauthenticated_client.post(
        "/expenses",
        json=VALID_PAYLOAD,
        headers={"Authorization": "Bearer test-secret-token"},
    )

    assert response.status_code == 201


def test_list_expenses_without_token_is_rejected(unauthenticated_client):
    response = unauthenticated_client.get("/expenses")

    assert response.status_code == 401


def test_read_root_requires_no_token(unauthenticated_client):
    response = unauthenticated_client.get("/")

    assert response.status_code == 200
