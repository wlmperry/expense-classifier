"""Focused API tests for the Expense endpoints.

These run through FastAPI's TestClient against the same isolated,
rollback-per-test expense_classifier_test database as
tests/test_expense_model.py (see the `client` and `db_session` fixtures in
tests/conftest.py) -- never against real DATABASE_URL data.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Expense

VALID_PAYLOAD = {
    "merchant": "DOLLAR GENERAL STORE #16600",
    "description": "S RED BULL 8.4C",
    "amount": "2.75",
    "expense_date": "2026-08-29",
}


def test_list_expenses_returns_persisted_expenses(client, db_session):
    first = Expense(
        merchant="DOLLAR GENERAL STORE #16600",
        description="S RED BULL 8.4C",
        amount=Decimal("2.75"),
        expense_date=date(2026, 8, 29),
    )
    second = Expense(
        merchant="ACME HARDWARE",
        description="HAMMER",
        amount=Decimal("19.99"),
        expense_date=date(2026, 1, 5),
    )
    db_session.add_all([first, second])
    db_session.flush()

    response = client.get("/expenses")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": first.id,
            "merchant": "DOLLAR GENERAL STORE #16600",
            "description": "S RED BULL 8.4C",
            "amount": "2.75",
            "expense_date": "2026-08-29",
        },
        {
            "id": second.id,
            "merchant": "ACME HARDWARE",
            "description": "HAMMER",
            "amount": "19.99",
            "expense_date": "2026-01-05",
        },
    ]


def test_list_expenses_returns_empty_list_when_no_expenses_exist(client):
    response = client.get("/expenses")

    assert response.status_code == 200
    assert response.json() == []


def test_create_expense_persists_and_returns_created_expense(client, db_session):
    response = client.post(
        "/expenses",
        json={
            "merchant": "DOLLAR GENERAL STORE #16600",
            "description": "S RED BULL 8.4C",
            "amount": "2.75",
            "expense_date": "2026-08-29",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["merchant"] == "DOLLAR GENERAL STORE #16600"
    assert body["description"] == "S RED BULL 8.4C"
    assert body["amount"] == "2.75"
    assert body["expense_date"] == "2026-08-29"

    persisted = db_session.get(Expense, body["id"])
    assert persisted is not None
    assert persisted.merchant == "DOLLAR GENERAL STORE #16600"
    assert persisted.description == "S RED BULL 8.4C"
    assert persisted.amount == Decimal("2.75")
    assert persisted.expense_date == date(2026, 8, 29)


def assert_rejected_and_not_persisted(client, db_session, payload):
    response = client.post("/expenses", json=payload)

    assert response.status_code == 422
    assert db_session.execute(select(Expense)).scalars().all() == []


@pytest.mark.parametrize("amount", [2.75, "2.755", "2.750", "0.00", "-5.00"])
def test_create_expense_rejects_invalid_amount(client, db_session, amount):
    assert_rejected_and_not_persisted(
        client, db_session, {**VALID_PAYLOAD, "amount": amount}
    )


@pytest.mark.parametrize("merchant", ["", "   "])
def test_create_expense_rejects_blank_merchant(client, db_session, merchant):
    assert_rejected_and_not_persisted(
        client, db_session, {**VALID_PAYLOAD, "merchant": merchant}
    )


def test_create_expense_rejects_missing_merchant(client, db_session):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "merchant"}
    assert_rejected_and_not_persisted(client, db_session, payload)


@pytest.mark.parametrize("description", ["", "   "])
def test_create_expense_rejects_blank_description(client, db_session, description):
    assert_rejected_and_not_persisted(
        client, db_session, {**VALID_PAYLOAD, "description": description}
    )


def test_create_expense_rejects_missing_description(client, db_session):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "description"}
    assert_rejected_and_not_persisted(client, db_session, payload)


@pytest.mark.parametrize(
    "expense_date",
    [
        "2026-02-30",  # invalid calendar date
        "09/20/2026",  # malformed/non-ISO string
        "2026-09-20T00:00:00",  # zero-time datetime string
        1758326400,  # JSON numeric timestamp
    ],
)
def test_create_expense_rejects_invalid_expense_date(client, db_session, expense_date):
    assert_rejected_and_not_persisted(
        client, db_session, {**VALID_PAYLOAD, "expense_date": expense_date}
    )


def test_create_expense_rejects_client_supplied_id(client, db_session):
    assert_rejected_and_not_persisted(client, db_session, {**VALID_PAYLOAD, "id": 999})
