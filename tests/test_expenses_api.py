"""Focused API tests for GET /expenses.

These run through FastAPI's TestClient against the same isolated,
rollback-per-test expense_classifier_test database as
tests/test_expense_model.py (see the `client` and `db_session` fixtures in
tests/conftest.py) -- never against real DATABASE_URL data.
"""

from datetime import date
from decimal import Decimal

from app.models import Expense


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
