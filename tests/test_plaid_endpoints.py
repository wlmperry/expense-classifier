"""Tests for the /plaid/* endpoints.

plaid_client is mocked throughout: these tests check that our own endpoint
logic builds the right request and turns Plaid's response into the right
Expense rows, not that Plaid's sandbox is reachable. That real-sandbox
behavior (including its asynchronous transaction-data population) was
verified by hand; see docs/architecture.md if that note doesn't exist yet
and needs adding.
"""

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from plaid.exceptions import ApiException

from app.models import Expense, PlaidItem


@pytest.fixture
def mock_plaid_client(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.main.get_plaid_client", lambda: mock)
    return mock


class _FakeHttpResponse:
    """Stands in for the urllib3 response ApiException normally wraps."""

    def __init__(self, status, reason, body):
        self.status = status
        self.reason = reason
        self.data = body

    def getheaders(self):
        return {}


def _plaid_api_exception(*, error_message="simulated Plaid failure"):
    body = json.dumps({"error_code": "SIMULATED", "error_message": error_message})
    return ApiException(http_resp=_FakeHttpResponse(400, "Bad Request", body))


def _sync_response(*, added=(), modified=(), removed=(), next_cursor="cursor-1", has_more=False):
    return SimpleNamespace(
        added=list(added),
        modified=list(modified),
        removed=list(removed),
        next_cursor=next_cursor,
        has_more=has_more,
    )


def test_get_plaid_item_status_returns_null_when_nothing_linked(client, db_session):
    response = client.get("/plaid/item")

    assert response.status_code == 200
    assert response.json() == {"item_id": None}


def test_get_plaid_item_status_returns_the_linked_item_id(client, db_session):
    _seed_plaid_item(db_session, item_id="item-abc123")

    response = client.get("/plaid/item")

    assert response.status_code == 200
    assert response.json() == {"item_id": "item-abc123"}


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


def test_create_link_token_returns_502_on_plaid_api_failure(client, mock_plaid_client):
    mock_plaid_client.link_token_create.side_effect = _plaid_api_exception(
        error_message="invalid client_id"
    )

    response = client.post("/plaid/link-token")

    assert response.status_code == 502
    assert "invalid client_id" in response.json()["detail"]


def test_create_link_token_returns_clean_500_when_plaid_not_configured(
    client, monkeypatch
):
    def raise_not_configured():
        raise RuntimeError("PLAID_CLIENT_ID and PLAID_SECRET are not set.")

    monkeypatch.setattr("app.main.get_plaid_client", raise_not_configured)

    response = client.post("/plaid/link-token")

    assert response.status_code == 500
    assert "not configured" in response.json()["detail"]


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


def test_exchange_public_token_is_idempotent_for_an_already_linked_item(
    client, db_session, mock_plaid_client
):
    """Relinking the same bank gives back the same item_id from Plaid;
    the endpoint should return the existing Item instead of trying (and
    failing, on the unique constraint) to insert a duplicate."""
    _seed_plaid_item(db_session, item_id="item-abc123")
    mock_plaid_client.item_public_token_exchange.return_value = SimpleNamespace(
        item_id="item-abc123", access_token="a-different-access-token"
    )

    response = client.post(
        "/plaid/exchange-public-token", json={"public_token": "public-sandbox-xyz"}
    )

    assert response.status_code == 201
    assert response.json() == {"item_id": "item-abc123"}
    assert db_session.query(PlaidItem).filter_by(item_id="item-abc123").count() == 1


def test_exchange_public_token_returns_502_on_plaid_api_failure(client, mock_plaid_client):
    mock_plaid_client.item_public_token_exchange.side_effect = _plaid_api_exception(
        error_message="invalid public_token"
    )

    response = client.post(
        "/plaid/exchange-public-token", json={"public_token": "expired-token"}
    )

    assert response.status_code == 502
    assert "invalid public_token" in response.json()["detail"]


def _seed_plaid_item(db_session, *, item_id="item-abc123", cursor=None) -> PlaidItem:
    item = PlaidItem(item_id=item_id, access_token="access-sandbox-abc123", cursor=cursor)
    db_session.add(item)
    db_session.flush()
    return item


def test_sync_creates_categorized_expense_for_each_outflow(
    client, db_session, mock_plaid_client
):
    _seed_plaid_item(db_session)
    mock_plaid_client.transactions_sync.return_value = _sync_response(
        added=[
            SimpleNamespace(
                transaction_id="txn-1",
                amount=12.0,
                merchant_name="McDonald's",
                name="MCDONALD'S F1234",
                date=date(2026, 10, 30),
            ),
            SimpleNamespace(
                transaction_id="txn-2",
                amount=6.33,
                merchant_name="Uber",
                name="Uber 072515 SF**POOL**",
                date=date(2026, 10, 31),
            ),
        ],
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    body = response.json()
    assert body["added_count"] == 2
    categories = {expense["merchant"]: expense["category"] for expense in body["added"]}
    assert categories == {"McDonald's": "Food & Dining", "Uber": "Transportation"}


def test_sync_skips_non_outflow_transactions(client, db_session, mock_plaid_client):
    _seed_plaid_item(db_session)
    mock_plaid_client.transactions_sync.return_value = _sync_response(
        added=[
            SimpleNamespace(
                transaction_id="txn-1",
                amount=-50.0,  # a deposit/refund, not an expense
                merchant_name="Employer Inc",
                name="Payroll deposit",
                date=date(2026, 10, 30),
            ),
        ],
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    assert response.json() == {"added_count": 0, "added": []}


def test_sync_persists_next_cursor_for_the_following_sync(
    client, db_session, mock_plaid_client
):
    item = _seed_plaid_item(db_session, cursor="cursor-0")
    mock_plaid_client.transactions_sync.return_value = _sync_response(next_cursor="cursor-1")

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    db_session.refresh(item)
    assert item.cursor == "cursor-1"
    request = mock_plaid_client.transactions_sync.call_args[0][0]
    assert request.cursor == "cursor-0"


def test_sync_passes_empty_cursor_on_first_sync(client, db_session, mock_plaid_client):
    _seed_plaid_item(db_session, cursor=None)
    mock_plaid_client.transactions_sync.return_value = _sync_response(next_cursor="cursor-1")

    client.post("/plaid/sync/item-abc123")

    request = mock_plaid_client.transactions_sync.call_args[0][0]
    assert request.cursor == ""


def test_sync_404s_for_unknown_item_id(client, mock_plaid_client):
    response = client.post("/plaid/sync/does-not-exist")

    assert response.status_code == 404
    mock_plaid_client.transactions_sync.assert_not_called()


def test_sync_does_not_reimport_a_transaction_already_persisted(
    client, db_session, mock_plaid_client
):
    """A transaction from an earlier sync (looked up by its own Plaid
    transaction_id, not the cursor) must not be inserted a second time."""
    _seed_plaid_item(db_session)
    db_session.add(
        Expense(
            merchant="McDonald's",
            description="MCDONALD'S F1234",
            amount="12.00",
            expense_date=date(2026, 10, 30),
            category="Food & Dining",
            plaid_transaction_id="txn-1",
        )
    )
    db_session.flush()
    mock_plaid_client.transactions_sync.return_value = _sync_response(
        added=[
            SimpleNamespace(
                transaction_id="txn-1",
                amount=12.0,
                merchant_name="McDonald's",
                name="MCDONALD'S F1234",
                date=date(2026, 10, 30),
            ),
        ],
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    assert response.json() == {"added_count": 0, "added": []}
    assert db_session.query(Expense).filter_by(plaid_transaction_id="txn-1").count() == 1


def test_sync_applies_a_modified_transaction_to_the_existing_expense(
    client, db_session, mock_plaid_client
):
    """A pending charge that later posts at a different amount arrives as
    `modified`, keyed by the same transaction_id -- it must update the
    existing Expense in place, not create a second one."""
    _seed_plaid_item(db_session)
    expense = Expense(
        merchant="McDonald's",
        description="MCDONALD'S F1234 (pending)",
        amount="10.00",
        expense_date=date(2026, 10, 30),
        category="Food & Dining",
        plaid_transaction_id="txn-1",
    )
    db_session.add(expense)
    db_session.flush()
    mock_plaid_client.transactions_sync.return_value = _sync_response(
        modified=[
            SimpleNamespace(
                transaction_id="txn-1",
                amount=12.5,
                merchant_name="McDonald's",
                name="MCDONALD'S F1234",
                date=date(2026, 10, 30),
            ),
        ],
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    assert response.json() == {"added_count": 0, "added": []}
    db_session.refresh(expense)
    assert str(expense.amount) == "12.50"
    assert expense.description == "MCDONALD'S F1234"


def test_sync_deletes_existing_expense_when_a_modified_transaction_turns_non_outflow(
    client, db_session, mock_plaid_client
):
    """A modified transaction can flip sign (e.g. a charge reversed into a
    refund); once it's no longer an outflow it should stop being an Expense."""
    _seed_plaid_item(db_session)
    db_session.add(
        Expense(
            merchant="McDonald's",
            description="MCDONALD'S F1234",
            amount="12.00",
            expense_date=date(2026, 10, 30),
            category="Food & Dining",
            plaid_transaction_id="txn-1",
        )
    )
    db_session.flush()
    mock_plaid_client.transactions_sync.return_value = _sync_response(
        modified=[
            SimpleNamespace(
                transaction_id="txn-1",
                amount=-12.00,
                merchant_name="McDonald's",
                name="MCDONALD'S F1234 REFUND",
                date=date(2026, 10, 31),
            ),
        ],
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    assert db_session.query(Expense).filter_by(plaid_transaction_id="txn-1").count() == 0


def test_sync_removes_an_expense_for_a_removed_transaction(
    client, db_session, mock_plaid_client
):
    _seed_plaid_item(db_session)
    db_session.add(
        Expense(
            merchant="McDonald's",
            description="MCDONALD'S F1234 (pending)",
            amount="10.00",
            expense_date=date(2026, 10, 30),
            category="Food & Dining",
            plaid_transaction_id="txn-1",
        )
    )
    db_session.flush()
    mock_plaid_client.transactions_sync.return_value = _sync_response(
        removed=[SimpleNamespace(transaction_id="txn-1")],
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    assert db_session.query(Expense).filter_by(plaid_transaction_id="txn-1").count() == 0


def test_sync_follows_pagination_until_has_more_is_false(
    client, db_session, mock_plaid_client
):
    _seed_plaid_item(db_session, cursor=None)
    page_one = _sync_response(
        added=[
            SimpleNamespace(
                transaction_id="txn-1",
                amount=5.0,
                merchant_name="Starbucks",
                name="STARBUCKS",
                date=date(2026, 10, 30),
            ),
        ],
        next_cursor="cursor-1",
        has_more=True,
    )
    page_two = _sync_response(
        added=[
            SimpleNamespace(
                transaction_id="txn-2",
                amount=7.0,
                merchant_name="Starbucks",
                name="STARBUCKS",
                date=date(2026, 10, 31),
            ),
        ],
        next_cursor="cursor-2",
        has_more=False,
    )
    mock_plaid_client.transactions_sync.side_effect = [page_one, page_two]

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 201
    assert response.json()["added_count"] == 2
    cursors_used = [
        call.args[0].cursor for call in mock_plaid_client.transactions_sync.call_args_list
    ]
    assert cursors_used == ["", "cursor-1"]
    item = db_session.query(PlaidItem).filter_by(item_id="item-abc123").one()
    assert item.cursor == "cursor-2"


def test_sync_returns_502_on_plaid_api_failure(client, db_session, mock_plaid_client):
    _seed_plaid_item(db_session)
    mock_plaid_client.transactions_sync.side_effect = _plaid_api_exception(
        error_message="ITEM_LOGIN_REQUIRED"
    )

    response = client.post("/plaid/sync/item-abc123")

    assert response.status_code == 502
    assert "ITEM_LOGIN_REQUIRED" in response.json()["detail"]
