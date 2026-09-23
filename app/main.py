from fastapi import Depends, FastAPI, status
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
    allow_methods=["GET", "POST"],
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

