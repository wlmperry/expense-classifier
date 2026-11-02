from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseRead

SortOption = Literal["expense_date", "-expense_date", "amount", "-amount"]

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

    See docs/architecture.md's Expense contract and "Established API
    decisions" for the request/response shape and wire-format guarantees.
    """
    expense = Expense(
        merchant=payload.merchant,
        description=payload.description,
        amount=payload.amount,
        expense_date=payload.expense_date,
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

