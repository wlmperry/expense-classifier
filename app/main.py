from fastapi import Depends, FastAPI, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseRead

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
def list_expenses(db: Session = Depends(get_db)) -> list[ExpenseRead]:
    """Return all persisted Expenses.

    See docs/architecture.md's Expense contract and "Established API
    decisions" for the response shape and wire-format guarantees.
    """
    return db.execute(select(Expense).order_by(Expense.id)).scalars().all()


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

