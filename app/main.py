from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.middleware.cors import CORSMiddleware
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import (
    SandboxPublicTokenCreateRequest,
)
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categorize import classify
from app.database import get_db
from app.models import Expense, PlaidItem
from app.plaid_client import plaid_client
from app.schemas import (
    ExpenseCreate,
    ExpenseRead,
    PlaidExchangePublicTokenRequest,
    PlaidExchangePublicTokenResponse,
    PlaidLinkTokenResponse,
    PlaidSandboxPublicTokenResponse,
    PlaidSyncResponse,
)

SortOption = Literal["expense_date", "-expense_date", "amount", "-amount"]
# Plaid's standard sandbox test institution ("First Platypus Bank"). Only
# meaningful in Sandbox -- it doesn't exist in Production.
_SANDBOX_INSTITUTION_ID = "ins_109508"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "DELETE"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status":"ok"}


@app.get("/expenses")
def list_expenses(
    limit: int | None = Query(default=None, gt=0, le=100),
    offset: int = Query(default=0, ge=0, le=9223372036854775807),
    merchant: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort: SortOption | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ExpenseRead]:
    """Return persisted Expenses, optionally filtered, sorted, and paginated.

    With no query parameters, behaves exactly as before: every Expense,
    ordered by id. merchant matches case-insensitively, anywhere in the
    field. date_from/date_to are inclusive. sort falls back to ordering by
    id as a tiebreaker, so results stay deterministic when several rows
    share a date or amount.

    See docs/architecture.md's Expense contract and "Established API
    decisions" for the response shape and wire-format guarantees.
    """
    query = select(Expense)

    if merchant is not None:
        query = query.where(Expense.merchant.icontains(merchant, autoescape=True))
    if date_from is not None:
        query = query.where(Expense.expense_date >= date_from)
    if date_to is not None:
        query = query.where(Expense.expense_date <= date_to)

    sort_columns = {
        "expense_date": Expense.expense_date.asc(),
        "-expense_date": Expense.expense_date.desc(),
        "amount": Expense.amount.asc(),
        "-amount": Expense.amount.desc(),
    }
    if sort is not None:
        query = query.order_by(sort_columns[sort], Expense.id)
    else:
        query = query.order_by(Expense.id)

    query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return db.execute(query).scalars().all()


@app.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)) -> ExpenseRead:
    """Persist one Expense and return the resulting persisted representation.

    If the client didn't supply a category, the baseline classifier picks
    one from the merchant/description instead of rejecting the request.

    See docs/architecture.md's Expense contract and "Established API
    decisions" for the request/response shape and wire-format guarantees.
    """
    category = payload.category or classify(payload.merchant, payload.description)
    expense = Expense(
        merchant=payload.merchant,
        description=payload.description,
        amount=payload.amount,
        expense_date=payload.expense_date,
        category=category,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int = Path(le=2147483647), db: Session = Depends(get_db)
) -> None:
    """Delete one persisted Expense by id, or 404 if it does not exist.

    expense_id is capped at Postgres's `integer` column max so an
    out-of-range id is rejected with 422 instead of crashing the
    database lookup.
    """
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        )

    db.delete(expense)
    db.commit()


@app.post("/plaid/link-token")
def create_plaid_link_token() -> PlaidLinkTokenResponse:
    """Create a Plaid Link token for the frontend to open Link with.

    client_user_id is hardcoded: there's no user/auth system in this
    project, so every linked bank belongs to the same single demo user.
    """
    request = LinkTokenCreateRequest(
        client_name="Expense Classifier",
        language="en",
        country_codes=[CountryCode("US")],
        user=LinkTokenCreateRequestUser(client_user_id="demo-user"),
        products=[Products("transactions")],
    )
    response = plaid_client.link_token_create(request)
    return PlaidLinkTokenResponse(
        link_token=response.link_token, expiration=response.expiration
    )


@app.post("/plaid/sandbox/public-token", status_code=status.HTTP_201_CREATED)
def create_sandbox_public_token() -> PlaidSandboxPublicTokenResponse:
    """Sandbox-only: simulate a user finishing Link against a fake bank,
    without needing the Link UI. Plaid's API itself rejects this call
    outside Sandbox, so it can't accidentally do anything in Production.
    """
    request = SandboxPublicTokenCreateRequest(
        institution_id=_SANDBOX_INSTITUTION_ID,
        initial_products=[Products("transactions")],
    )
    response = plaid_client.sandbox_public_token_create(request)
    return PlaidSandboxPublicTokenResponse(public_token=response.public_token)


@app.post("/plaid/exchange-public-token", status_code=status.HTTP_201_CREATED)
def exchange_public_token(
    payload: PlaidExchangePublicTokenRequest, db: Session = Depends(get_db)
) -> PlaidExchangePublicTokenResponse:
    """Exchange a short-lived public_token for a durable access_token, and
    persist the resulting Item so later syncs can use it.
    """
    request = ItemPublicTokenExchangeRequest(public_token=payload.public_token)
    response = plaid_client.item_public_token_exchange(request)

    item = PlaidItem(item_id=response.item_id, access_token=response.access_token)
    db.add(item)
    db.commit()
    return PlaidExchangePublicTokenResponse(item_id=item.item_id)


@app.post("/plaid/sync/{item_id}", status_code=status.HTTP_201_CREATED)
def sync_plaid_transactions(item_id: str, db: Session = Depends(get_db)) -> PlaidSyncResponse:
    """Pull new transactions for a linked Item and persist each as a
    categorized Expense.

    transactions_sync is cursor-based: an empty cursor (the first call for
    this Item) returns everything available; passing back the cursor from
    a previous call returns only what changed since then. Only outflows
    (amount > 0, Plaid's convention for money leaving the account) become
    Expenses -- deposits and refunds aren't expenses. Plaid already tags
    each transaction with its own category, but it's deliberately ignored
    here in favor of this project's own classifier.
    """
    item = db.execute(
        select(PlaidItem).where(PlaidItem.item_id == item_id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plaid item not found"
        )

    request = TransactionsSyncRequest(access_token=item.access_token, cursor=item.cursor or "")
    response = plaid_client.transactions_sync(request)

    added_expenses = []
    for transaction in response.added:
        if transaction.amount <= 0:
            continue
        merchant = transaction.merchant_name or transaction.name
        expense = Expense(
            merchant=merchant,
            description=transaction.name,
            amount=Decimal(str(transaction.amount)).quantize(Decimal("0.01")),
            expense_date=transaction.date,
            category=classify(merchant, transaction.name),
        )
        db.add(expense)
        added_expenses.append(expense)

    item.cursor = response.next_cursor
    db.commit()
    for expense in added_expenses:
        db.refresh(expense)

    return PlaidSyncResponse(added_count=len(added_expenses), added=added_expenses)

