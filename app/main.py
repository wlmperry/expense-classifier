import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Literal, TypeVar

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.middleware.cors import CORSMiddleware
from plaid.exceptions import ApiException
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
from plaid.model.transaction import Transaction
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_api_token, require_auth_token
from app.categorize import classify
from app.database import get_db
from app.models import Expense, PlaidItem
from app.plaid_client import get_plaid_client
from app.schemas import (
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    PlaidExchangePublicTokenRequest,
    PlaidExchangePublicTokenResponse,
    PlaidItemStatusResponse,
    PlaidLinkTokenResponse,
    PlaidSandboxPublicTokenResponse,
    PlaidSyncResponse,
)

SortOption = Literal["expense_date", "-expense_date", "amount", "-amount"]
# Plaid's standard sandbox test institution ("First Platypus Bank"). Only
# meaningful in Sandbox -- it doesn't exist in Production.
_SANDBOX_INSTITUTION_ID = "ins_109508"

_PlaidResult = TypeVar("_PlaidResult")


def _call_plaid(operation: Callable[[], _PlaidResult], *, action: str) -> _PlaidResult:
    """Run a Plaid SDK call, translating failures into a clean HTTPException
    instead of an unhandled 500.

    RuntimeError is what get_plaid_client() itself raises when
    PLAID_CLIENT_ID/PLAID_SECRET aren't configured -- a server
    misconfiguration, not the caller's fault, but still worth a clear detail.
    ApiException is what the Plaid SDK raises for an API-level failure (an
    invalid/expired public_token, ITEM_LOGIN_REQUIRED, etc).
    """
    try:
        return operation()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not {action}: Plaid is not configured ({exc})",
        ) from exc
    except ApiException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not {action}: {_plaid_error_detail(exc)}",
        ) from exc


def _plaid_error_detail(exc: ApiException) -> str:
    """Pull Plaid's own error_message out of an ApiException's response
    body when present, falling back to the HTTP reason phrase."""
    if exc.body:
        try:
            body = json.loads(exc.body)
        except (TypeError, ValueError):
            body = None
        if isinstance(body, dict) and body.get("error_message"):
            return body["error_message"]
    return exc.reason or "Plaid request failed"


def _expense_from_transaction(transaction: Transaction) -> Expense | None:
    """Build an unsaved Expense from a Plaid transaction, or None if it's
    not an outflow (amount > 0, Plaid's convention for money leaving the
    account) -- deposits and refunds aren't expenses. Plaid already tags
    each transaction with its own category, but it's deliberately ignored
    here in favor of this project's own classifier."""
    if transaction.amount <= 0:
        return None
    merchant = transaction.merchant_name or transaction.name
    return Expense(
        merchant=merchant,
        description=transaction.name,
        amount=Decimal(str(transaction.amount)).quantize(Decimal("0.01")),
        expense_date=transaction.date,
        category=classify(merchant, transaction.name),
        plaid_transaction_id=transaction.transaction_id,
    )

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Fails fast at startup, like app/database.py's engine construction
    # already does for DATABASE_URL, instead of on the first protected
    # request. Not checked at import time: tests override API_AUTH_TOKEN
    # per-test, after this module has already been imported.
    get_api_token()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status":"ok"}


@app.get("/expenses", dependencies=[Depends(require_auth_token)])
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


@app.post(
    "/expenses",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth_token)],
)
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


@app.patch("/expenses/{expense_id}", dependencies=[Depends(require_auth_token)])
def update_expense(
    payload: ExpenseUpdate,
    expense_id: int = Path(le=2147483647),
    db: Session = Depends(get_db),
) -> ExpenseRead:
    """Partially update one persisted Expense by id, or 404 if it does not exist.

    Only fields present in the request body are changed; an omitted field
    keeps its existing value. Unlike POST /expenses, category is never
    re-derived from the classifier here -- a client that wants a different
    category has to say so explicitly.
    """
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)

    db.commit()
    db.refresh(expense)
    return expense


@app.delete(
    "/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_auth_token)],
)
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


@app.get("/plaid/item", dependencies=[Depends(require_auth_token)])
def get_plaid_item_status(db: Session = Depends(get_db)) -> PlaidItemStatusResponse:
    """Report whether this project's single demo user already has a bank
    linked, so the frontend can disable Connect bank instead of letting a
    second Link session run.

    This matters because a repeat Link session mints a brand-new item_id
    with its own fresh transaction_ids -- exchange_public_token's
    idempotency check (same item_id already saved) never gets a chance to
    fire, and dedup-by-transaction_id in the sync endpoint can't catch
    transaction_ids it's never seen before. Only one Item is ever expected
    to exist (client_user_id is hardcoded below), so the first one found is
    reported.
    """
    item = db.execute(select(PlaidItem).order_by(PlaidItem.id)).scalars().first()
    return PlaidItemStatusResponse(item_id=item.item_id if item is not None else None)


@app.post("/plaid/link-token", dependencies=[Depends(require_auth_token)])
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
    response = _call_plaid(
        lambda: get_plaid_client().link_token_create(request),
        action="create Plaid link token",
    )
    return PlaidLinkTokenResponse(
        link_token=response.link_token, expiration=response.expiration
    )


@app.post(
    "/plaid/sandbox/public-token",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth_token)],
)
def create_sandbox_public_token() -> PlaidSandboxPublicTokenResponse:
    """Sandbox-only: simulate a user finishing Link against a fake bank,
    without needing the Link UI. Plaid's API itself rejects this call
    outside Sandbox, so it can't accidentally do anything in Production.
    """
    request = SandboxPublicTokenCreateRequest(
        institution_id=_SANDBOX_INSTITUTION_ID,
        initial_products=[Products("transactions")],
    )
    response = _call_plaid(
        lambda: get_plaid_client().sandbox_public_token_create(request),
        action="create Plaid sandbox public token",
    )
    return PlaidSandboxPublicTokenResponse(public_token=response.public_token)


@app.post(
    "/plaid/exchange-public-token",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth_token)],
)
def exchange_public_token(
    payload: PlaidExchangePublicTokenRequest, db: Session = Depends(get_db)
) -> PlaidExchangePublicTokenResponse:
    """Exchange a short-lived public_token for a durable access_token, and
    persist the resulting Item so later syncs can use it.

    item_id is checked for an existing row first: relinking the same bank
    returns the same item_id from Plaid, and inserting it again would hit
    PlaidItem.item_id's unique constraint. Returning the existing Item
    instead makes this endpoint idempotent rather than erroring.
    """
    request = ItemPublicTokenExchangeRequest(public_token=payload.public_token)
    response = _call_plaid(
        lambda: get_plaid_client().item_public_token_exchange(request),
        action="exchange Plaid public token",
    )

    existing = db.execute(
        select(PlaidItem).where(PlaidItem.item_id == response.item_id)
    ).scalar_one_or_none()
    if existing is not None:
        return PlaidExchangePublicTokenResponse(item_id=existing.item_id)

    item = PlaidItem(item_id=response.item_id, access_token=response.access_token)
    db.add(item)
    db.commit()
    return PlaidExchangePublicTokenResponse(item_id=item.item_id)


@app.post(
    "/plaid/sync/{item_id}",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth_token)],
)
def sync_plaid_transactions(item_id: str, db: Session = Depends(get_db)) -> PlaidSyncResponse:
    """Pull every new, changed, and removed transaction for a linked Item
    since its last sync, and apply each to this project's own Expense rows.

    transactions_sync is cursor-based and paginated: an empty cursor (the
    first call for this Item) returns everything available; passing back
    the cursor from a previous call returns only what changed since then.
    has_more indicates another page is waiting, so this loops -- following
    Plaid's documented pagination contract -- until a response says
    has_more is false. Each transaction is looked up by its own Plaid
    transaction_id (not the Expense id) so a transaction already imported
    by an earlier sync is updated in place instead of duplicated, and a
    transaction Plaid later removes (e.g. a pending charge that never
    posts) is deleted here too.

    added_count/added describe only genuinely new Expenses -- a modified
    transaction that already has a matching Expense updates it in place
    without counting as "added".
    """
    item = db.execute(
        select(PlaidItem).where(PlaidItem.item_id == item_id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plaid item not found"
        )

    new_expenses: list[Expense] = []
    cursor = item.cursor or ""
    has_more = True
    while has_more:
        request = TransactionsSyncRequest(access_token=item.access_token, cursor=cursor)
        response = _call_plaid(
            lambda req=request: get_plaid_client().transactions_sync(req),
            action="sync Plaid transactions",
        )

        for transaction in response.added:
            if _find_expense_by_transaction_id(db, transaction.transaction_id) is not None:
                continue  # already imported by an earlier call in this same loop/sync
            expense = _expense_from_transaction(transaction)
            if expense is None:
                continue  # not an outflow
            db.add(expense)
            new_expenses.append(expense)

        for transaction in response.modified:
            existing = _find_expense_by_transaction_id(db, transaction.transaction_id)
            if existing is None:
                expense = _expense_from_transaction(transaction)
                if expense is None:
                    continue
                db.add(expense)
                new_expenses.append(expense)
                continue
            if transaction.amount <= 0:
                db.delete(existing)
                if existing in new_expenses:
                    new_expenses.remove(existing)
                continue
            merchant = transaction.merchant_name or transaction.name
            existing.merchant = merchant
            existing.description = transaction.name
            existing.amount = Decimal(str(transaction.amount)).quantize(Decimal("0.01"))
            existing.expense_date = transaction.date
            existing.category = classify(merchant, transaction.name)

        for removed in response.removed:
            existing = _find_expense_by_transaction_id(db, removed.transaction_id)
            if existing is not None:
                db.delete(existing)
                if existing in new_expenses:
                    new_expenses.remove(existing)

        cursor = response.next_cursor
        has_more = response.has_more

    item.cursor = cursor
    # flush (not commit) first: it assigns each new Expense's id via
    # RETURNING without expiring any attribute, so ExpenseRead can read
    # every field straight off these objects with no extra per-row SELECT.
    db.flush()
    results = [ExpenseRead.model_validate(expense) for expense in new_expenses]
    db.commit()

    return PlaidSyncResponse(added_count=len(results), added=results)


def _find_expense_by_transaction_id(db: Session, transaction_id: str) -> Expense | None:
    return db.execute(
        select(Expense).where(Expense.plaid_transaction_id == transaction_id)
    ).scalar_one_or_none()

