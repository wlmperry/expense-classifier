"""Focused PostgreSQL persistence tests for the Expense model.

These exercise real PostgreSQL behavior (unconstrained NUMERIC scale, CHECK
constraints) against the dedicated expense_classifier_test database, so an
in-memory or SQLite substitute would not accurately represent them.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Expense

VALID_KWARGS = {
    "merchant": "DOLLAR GENERAL STORE #16600",
    "description": "S RED BULL 8.4C",
    "amount": Decimal("2.75"),
    "expense_date": date(2026, 8, 29),
}


def test_round_trip_preserves_contract_values(db_session):
    expense = Expense(**VALID_KWARGS)
    db_session.add(expense)
    db_session.flush()
    db_session.expire_all()

    fetched = db_session.get(Expense, expense.id)

    assert fetched.merchant == VALID_KWARGS["merchant"]
    assert fetched.description == VALID_KWARGS["description"]
    assert fetched.amount == VALID_KWARGS["amount"]
    assert fetched.expense_date == VALID_KWARGS["expense_date"]


def test_id_is_generated_on_flush(db_session):
    expense = Expense(**VALID_KWARGS)
    assert expense.id is None

    db_session.add(expense)
    db_session.flush()

    assert isinstance(expense.id, int)


@pytest.mark.parametrize("amount", [Decimal(0), Decimal("-5.00")])
def test_non_positive_amount_is_rejected(db_session, amount):
    db_session.add(Expense(**{**VALID_KWARGS, "amount": amount}))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("amount", [Decimal("2.755"), Decimal("2.750")])
def test_amount_with_more_than_two_decimal_places_is_rejected(db_session, amount):
    db_session.add(Expense(**{**VALID_KWARGS, "amount": amount}))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("merchant", ["", "   "])
def test_blank_merchant_is_rejected(db_session, merchant):
    db_session.add(Expense(**{**VALID_KWARGS, "merchant": merchant}))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("description", ["", "   "])
def test_blank_description_is_rejected(db_session, description):
    db_session.add(Expense(**{**VALID_KWARGS, "description": description}))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("overrides", [{"merchant": None}, {"description": None}])
def test_none_required_field_is_rejected(db_session, overrides):
    db_session.add(Expense(**{**VALID_KWARGS, **overrides}))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_missing_merchant_is_rejected(db_session):
    kwargs = {k: v for k, v in VALID_KWARGS.items() if k != "merchant"}
    db_session.add(Expense(**kwargs))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_missing_description_is_rejected(db_session):
    kwargs = {k: v for k, v in VALID_KWARGS.items() if k != "description"}
    db_session.add(Expense(**kwargs))

    with pytest.raises(IntegrityError):
        db_session.flush()
