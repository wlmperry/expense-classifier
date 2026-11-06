"""Tests for the /plaid/* endpoints.

plaid_client is mocked throughout: these tests check that our own endpoint
logic builds the right request and turns Plaid's response into the right
Expense rows, not that Plaid's sandbox is reachable. That real-sandbox
behavior (including its asynchronous transaction-data population) was
verified by hand; see docs/architecture.md if that note doesn't exist yet
and needs adding.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models import PlaidItem


@pytest.fixture
def mock_plaid_client(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.main.get_plaid_client", lambda: mock)
    return mock


def test_create_link_token_returns_link_token_and_expiration(client, mock_plaid_client):
    expiration = datetime(2026, 11, 2, 18, 0, 0, tzinfo=timezone.utc)
    mock_plaid_client.link_token_create.return_value = SimpleNamespace(
        link_token="link-sandbox-abc123", expiration=expiration
    )

    response = client.post("/plaid/link-token")

    assert response.status_code == 200
    assert response.json() == {
        "link_token": "link-sandbox-abc123",
        "expiration": "2026-11-02T18:00:00Z",
    }


def test_create_sandbox_public_token_returns_public_token(client, mock_plaid_client):
    mock_plaid_client.sandbox_public_token_create.return_value = SimpleNamespace(
        public_token="public-sandbox-abc123"
    )

    response = client.post("/plaid/sandbox/public-token")

    assert response.status_code == 201
    assert response.json() == {"public_token": "public-sandbox-abc123"}


def test_exchange_public_token_persists_item_and_returns_item_id(
    client, db_session, mock_plaid_client
):
    mock_plaid_client.item_public_token_exchange.return_value = SimpleNamespace(
        item_id="item-abc123", access_token="access-sandbox-abc123"
    )

    response = client.post(
        "/plaid/exchange-public-token", json={"public_token": "public-sandbox-abc123"}
    )

    assert response.status_code == 201
    assert response.json() == {"item_id": "item-abc123"}

    persisted = (
        db_session.query(PlaidItem).filter_by(item_id="item-abc123").one()
    )
    assert persisted.access_token == "access-sandbox-abc123"
    assert persisted.cursor is None


def test_exchange_public_token_rejects_unknown_fields(client, mock_plaid_client):
    response = client.post(
        "/plaid/exchange-public-token",
        json={"public_token": "public-sandbox-abc123", "extra": "nope"},
    )

    assert response.status_code == 422
    mock_plaid_client.item_public_token_exchange.assert_not_called()


def _seed_plaid_item(db_session, *, item_id="item-abc123", cursor=None) -> PlaidItem:
    item = PlaidItem(item_id=item_id, access_token="access-sandbox-abc123", cursor=cursor)
    db_session.add(item)
    db_session.flush()
    return item


def test_sync_creates_categorized_expense_for_each_outflow(
    client, db_session, mock_plaid_client
):
    _seed_plaid_item(db_session)
    mock_plaid_client.transactions_sync.return_value = SimpleNamespace(
        added=[
            SimpleNamespace(
                amount=12.0,
                merchant_name="McDonald's",
                name="MCDONALD'S F1234",
                date=date(2026, 10, 30),
            ),
            SimpleNamespace(
                amount=6.33,
                merchant_name="Uber",
                name="Uber 072515 SF**POOL**",
                date=date(2026, 10, 31),
            ),
        ],
        next_cursor="cursor-1",
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    body = response.json()
    assert body["added_count"] == 2
    categories = {expense["merchant"]: expense["category"] for expense in body["added"]}
    assert categories == {"McDonald's": "Food & Dining", "Uber": "Transportation"}


def test_sync_skips_non_outflow_transactions(client, db_session, mock_plaid_client):
    _seed_plaid_item(db_session)
    mock_plaid_client.transactions_sync.return_value = SimpleNamespace(
        added=[
            SimpleNamespace(
                amount=-50.0,  # a deposit/refund, not an expense
                merchant_name="Employer Inc",
                name="Payroll deposit",
                date=date(2026, 10, 30),
            ),
        ],
        next_cursor="cursor-1",
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    assert response.json() == {"added_count": 0, "added": []}


def test_sync_persists_next_cursor_for_the_following_sync(
    client, db_session, mock_plaid_client
):
    item = _seed_plaid_item(db_session, cursor="cursor-0")
    mock_plaid_client.transactions_sync.return_value = SimpleNamespace(
        added=[], next_cursor="cursor-1"
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    db_session.refresh(item)
    assert item.cursor == "cursor-1"
    request = mock_plaid_client.transactions_sync.call_args[0][0]
    assert request.cursor == "cursor-0"


def test_sync_passes_empty_cursor_on_first_sync(client, db_session, mock_plaid_client):
    _seed_plaid_item(db_session, cursor=None)
    mock_plaid_client.transactions_sync.return_value = SimpleNamespace(
        added=[], next_cursor="cursor-1"
    )

    client.post("/plaid/sync/item-abc123")

    request = mock_plaid_client.transactions_sync.call_args[0][0]
    assert request.cursor == ""


def test_sync_404s_for_unknown_item_id(client, mock_plaid_client):
    response = client.post("/plaid/sync/does-not-exist")

    assert response.status_code == 404
    mock_plaid_client.transactions_sync.assert_not_called()
