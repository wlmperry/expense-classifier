"""Each user sees and changes only their own expenses and bank link (Issue #44).

Every test here is logged in as `user` (through the `client` fixture) and
puts data under `other_user`, then checks that `user` can't reach it.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.models import Expense, PlaidItem


@pytest.fixture
def mock_plaid_client(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.main.get_plaid_client", lambda: mock)
    return mock


def _add_expense(db_session, owner, merchant: str) -> Expense:
    expense = Expense(
        user_id=owner.id,
        merchant=merchant,
        description="Test purchase",
        amount=Decimal("10.00"),
        expense_date=date(2026, 9, 1),
        category="Other",
    )
    db_session.add(expense)
    db_session.flush()
    return expense


def _add_plaid_item(db_session, owner, item_id: str) -> PlaidItem:
    item = PlaidItem(user_id=owner.id, item_id=item_id, access_token="access-sandbox-other")
    db_session.add(item)
    db_session.flush()
    return item


# --- Expenses ---


def test_list_returns_only_the_current_users_expenses(client, db_session, user, other_user):
    _add_expense(db_session, user, "Mine")
    _add_expense(db_session, other_user, "Theirs")

    response = client.get("/expenses")

    assert [e["merchant"] for e in response.json()] == ["Mine"]


def test_create_saves_the_expense_under_the_current_user(client, db_session, user):
    response = client.post(
        "/expenses",
        json={
            "merchant": "Corner Store",
            "description": "Coffee",
            "amount": "3.50",
            "expense_date": "2026-09-01",
        },
    )

    saved = db_session.get(Expense, response.json()["id"])
    assert saved.user_id == user.id


def test_cannot_update_another_users_expense(client, db_session, other_user):
    theirs = _add_expense(db_session, other_user, "Theirs")

    response = client.patch(f"/expenses/{theirs.id}", json={"merchant": "Hacked"})

    assert response.status_code == 404
    db_session.refresh(theirs)
    assert theirs.merchant == "Theirs"


def test_cannot_delete_another_users_expense(client, db_session, other_user):
    theirs = _add_expense(db_session, other_user, "Theirs")

    response = client.delete(f"/expenses/{theirs.id}")

    assert response.status_code == 404
    assert db_session.get(Expense, theirs.id) is not None


def test_another_users_expense_looks_the_same_as_a_missing_one(client, db_session, other_user):
    theirs = _add_expense(db_session, other_user, "Theirs")

    theirs_response = client.delete(f"/expenses/{theirs.id}")
    missing_response = client.delete("/expenses/2147483647")

    assert theirs_response.status_code == missing_response.status_code == 404
    assert theirs_response.json() == missing_response.json()


# --- Plaid ---


def test_bank_list_ignores_another_users_linked_bank(
    client, db_session, other_user, mock_plaid_client
):
    _add_plaid_item(db_session, other_user, "item-theirs")

    response = client.get("/plaid/items")

    assert response.json() == []
    # Their bank has no institution saved, but it isn't ours to look up.
    mock_plaid_client.item_get.assert_not_called()


def test_cannot_sync_another_users_bank(client, db_session, other_user, mock_plaid_client):
    _add_plaid_item(db_session, other_user, "item-theirs")

    response = client.post("/plaid/sync/item-theirs")

    assert response.status_code == 404
    mock_plaid_client.transactions_sync.assert_not_called()


def test_link_token_identifies_the_current_user_to_plaid(client, user, mock_plaid_client):
    mock_plaid_client.link_token_create.return_value = SimpleNamespace(
        link_token="link-sandbox-abc123", expiration="2026-11-02T18:00:00Z"
    )

    client.post("/plaid/link-token")

    request = mock_plaid_client.link_token_create.call_args.args[0]
    assert request.user.client_user_id == str(user.id)


def test_exchange_saves_the_bank_under_the_current_user(
    client, db_session, user, mock_plaid_client
):
    mock_plaid_client.item_public_token_exchange.return_value = SimpleNamespace(
        item_id="item-mine", access_token="access-sandbox-mine"
    )

    client.post("/plaid/exchange-public-token", json={"public_token": "public-sandbox-1"})

    item = db_session.execute(
        select(PlaidItem).where(PlaidItem.item_id == "item-mine")
    ).scalar_one()
    assert item.user_id == user.id


def test_exchange_refuses_a_bank_already_linked_to_another_user(
    client, db_session, other_user, mock_plaid_client
):
    _add_plaid_item(db_session, other_user, "item-theirs")
    mock_plaid_client.item_public_token_exchange.return_value = SimpleNamespace(
        item_id="item-theirs", access_token="access-sandbox-new"
    )

    response = client.post(
        "/plaid/exchange-public-token", json={"public_token": "public-sandbox-2"}
    )

    assert response.status_code == 409
    item = db_session.execute(
        select(PlaidItem).where(PlaidItem.item_id == "item-theirs")
    ).scalar_one()
    assert item.user_id == other_user.id


def test_sync_never_deletes_another_users_expense(
    client, db_session, user, other_user, mock_plaid_client
):
    """Even if Plaid reported a transaction id as removed that, somehow,
    belongs to another user's expense, this user's sync must leave it alone."""
    _add_plaid_item(db_session, user, "item-mine")
    theirs = _add_expense(db_session, other_user, "Theirs")
    theirs.plaid_transaction_id = "txn-shared"
    db_session.flush()
    mock_plaid_client.transactions_sync.return_value = SimpleNamespace(
        added=[],
        modified=[],
        removed=[SimpleNamespace(transaction_id="txn-shared")],
        next_cursor="c1",
        has_more=False,
    )

    response = client.post("/plaid/sync/item-mine")

    assert response.status_code == 201
    assert db_session.get(Expense, theirs.id) is not None


def test_synced_expenses_belong_to_the_current_user(
    client, db_session, user, mock_plaid_client
):
    _add_plaid_item(db_session, user, "item-mine")
    transaction = SimpleNamespace(
        transaction_id="txn-1",
        amount=12.5,
        merchant_name="Corner Store",
        name="CORNER STORE 123",
        date=date(2026, 9, 2),
    )
    mock_plaid_client.transactions_sync.return_value = SimpleNamespace(
        added=[transaction], modified=[], removed=[], next_cursor="c1", has_more=False
    )

    response = client.post("/plaid/sync/item-mine")

    saved = db_session.get(Expense, response.json()["added"][0]["id"])
    assert saved.user_id == user.id
