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


def _seed_expenses_for_pagination_filter_sort(db_session):
    """Four Expenses whose id order, date order, and amount order all
    differ, so a test can't pass by accident just because two orderings
    happen to coincide."""
    expenses = [
        Expense(
            merchant="Corner Store",
            description="Coffee",
            amount=Decimal("19.99"),
            expense_date=date(2026, 2, 15),
        ),
        Expense(
            merchant="ACME Hardware",
            description="Hammer",
            amount=Decimal("42.00"),
            expense_date=date(2026, 1, 1),
        ),
        Expense(
            merchant="Corner Store",
            description="Snacks",
            amount=Decimal("3.50"),
            expense_date=date(2026, 2, 1),
        ),
        Expense(
            merchant="Gas Station",
            description="Fuel",
            amount=Decimal("7.25"),
            expense_date=date(2026, 1, 15),
        ),
    ]
    db_session.add_all(expenses)
    db_session.flush()
    return expenses


def test_list_expenses_limit_restricts_number_of_results(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?limit=2")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[0].id, expenses[1].id]


def test_list_expenses_offset_skips_earlier_results(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?offset=2")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[2].id, expenses[3].id]


def test_list_expenses_limit_and_offset_combine_for_a_page(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?limit=1&offset=1")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[1].id]


@pytest.mark.parametrize("limit", [0, -1])
def test_list_expenses_rejects_non_positive_limit(client, db_session, limit):
    _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get(f"/expenses?limit={limit}")

    assert response.status_code == 422


def test_list_expenses_rejects_limit_above_maximum(client, db_session):
    _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?limit=101")

    assert response.status_code == 422


def test_list_expenses_rejects_negative_offset(client, db_session):
    _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?offset=-1")

    assert response.status_code == 422


def test_list_expenses_filters_by_merchant_substring_case_insensitive(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?merchant=store")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[0].id, expenses[2].id]


def test_list_expenses_filters_by_date_from(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?date_from=2026-02-01")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[0].id, expenses[2].id]


def test_list_expenses_filters_by_date_to(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?date_to=2026-01-15")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[1].id, expenses[3].id]


def test_list_expenses_filters_by_date_range_inclusive_on_both_ends(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?date_from=2026-01-15&date_to=2026-02-01")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[2].id, expenses[3].id]


def test_list_expenses_sorts_by_expense_date_ascending(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?sort=expense_date")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [
        expenses[1].id,
        expenses[3].id,
        expenses[2].id,
        expenses[0].id,
    ]


def test_list_expenses_sorts_by_expense_date_descending(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?sort=-expense_date")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [
        expenses[0].id,
        expenses[2].id,
        expenses[3].id,
        expenses[1].id,
    ]


def test_list_expenses_sorts_by_amount_ascending(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?sort=amount")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [
        expenses[2].id,
        expenses[3].id,
        expenses[0].id,
        expenses[1].id,
    ]


def test_list_expenses_sorts_by_amount_descending(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?sort=-amount")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [
        expenses[1].id,
        expenses[0].id,
        expenses[3].id,
        expenses[2].id,
    ]


def test_list_expenses_rejects_invalid_sort_value(client, db_session):
    _seed_expenses_for_pagination_filter_sort(db_session)

    response = client.get("/expenses?sort=bogus")

    assert response.status_code == 422


def test_list_expenses_combines_filter_sort_and_pagination(client, db_session):
    expenses = _seed_expenses_for_pagination_filter_sort(db_session)

    # merchant="a" matches ACME Hardware and Gas Station only (neither
    # "Corner Store" contains an "a"), then the highest amount of those two
    # wins under sort=-amount, and limit=1 keeps just that one.
    response = client.get("/expenses?merchant=a&sort=-amount&limit=1")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [expenses[1].id]


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


def test_delete_expense_removes_it_and_returns_204(client, db_session):
    expense = Expense(
        merchant="DOLLAR GENERAL STORE #16600",
        description="S RED BULL 8.4C",
        amount=Decimal("2.75"),
        expense_date=date(2026, 8, 29),
    )
    db_session.add(expense)
    db_session.flush()

    response = client.delete(f"/expenses/{expense.id}")

    assert response.status_code == 204
    assert expense.id not in [e["id"] for e in client.get("/expenses").json()]


def test_delete_expense_returns_404_when_not_found(client):
    response = client.delete("/expenses/999999")

    assert response.status_code == 404


def test_delete_expense_rejects_id_above_postgres_integer_max(client):
    response = client.delete("/expenses/99999999999999999999")

    assert response.status_code == 422


def test_delete_expense_twice_returns_404_on_second_call(client, db_session):
    expense = Expense(
        merchant="DOLLAR GENERAL STORE #16600",
        description="S RED BULL 8.4C",
        amount=Decimal("2.75"),
        expense_date=date(2026, 8, 29),
    )
    db_session.add(expense)
    db_session.flush()

    first = client.delete(f"/expenses/{expense.id}")
    second = client.delete(f"/expenses/{expense.id}")

    assert first.status_code == 204
    assert second.status_code == 404
