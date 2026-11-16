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
    "category": "Other",
}


def test_round_trip_preserves_contract_values(user, db_session):
    expense = Expense(**VALID_KWARGS, user_id=user.id)
    db_session.add(expense)
    db_session.flush()
    db_session.expire_all()

    fetched = db_session.get(Expense, expense.id)

    assert fetched.merchant == VALID_KWARGS["merchant"]
    assert fetched.description == VALID_KWARGS["description"]
    assert fetched.amount == VALID_KWARGS["amount"]
    assert fetched.expense_date == VALID_KWARGS["expense_date"]


def test_id_is_generated_on_flush(user, db_session):
    expense = Expense(**VALID_KWARGS, user_id=user.id)
    assert expense.id is None

    db_session.add(expense)
    db_session.flush()

    assert isinstance(expense.id, int)


@pytest.mark.parametrize("amount", [Decimal(0), Decimal("-5.00")])
def test_non_positive_amount_is_rejected(user, db_session, amount):
    db_session.add(Expense(**{**VALID_KWARGS, "amount": amount}, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("amount", [Decimal("2.755"), Decimal("2.750")])
def test_amount_with_more_than_two_decimal_places_is_rejected(user, db_session, amount):
    db_session.add(Expense(**{**VALID_KWARGS, "amount": amount}, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("confidence", [Decimal("-0.01"), Decimal("1.01")])
def test_confidence_outside_zero_to_one_is_rejected(user, db_session, confidence):
    db_session.add(Expense(**{**VALID_KWARGS, "confidence": confidence}, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("confidence", [Decimal(0), Decimal(1), Decimal("0.5"), None])
def test_confidence_within_zero_to_one_or_null_is_accepted(user, db_session, confidence):
    db_session.add(Expense(**{**VALID_KWARGS, "confidence": confidence}, user_id=user.id))

    db_session.flush()  # must not raise


@pytest.mark.parametrize("merchant", ["", "   "])
def test_blank_merchant_is_rejected(user, db_session, merchant):
    db_session.add(Expense(**{**VALID_KWARGS, "merchant": merchant}, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("description", ["", "   "])
def test_blank_description_is_rejected(user, db_session, description):
    db_session.add(Expense(**{**VALID_KWARGS, "description": description}, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("overrides", [{"merchant": None}, {"description": None}])
def test_none_required_field_is_rejected(user, db_session, overrides):
    db_session.add(Expense(**{**VALID_KWARGS, **overrides}, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_missing_merchant_is_rejected(user, db_session):
    kwargs = {k: v for k, v in VALID_KWARGS.items() if k != "merchant"}
    db_session.add(Expense(**kwargs, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_missing_description_is_rejected(user, db_session):
    kwargs = {k: v for k, v in VALID_KWARGS.items() if k != "description"}
    db_session.add(Expense(**kwargs, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()
