from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Expense
from app.schemas import ExpenseRead

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/expenses")
def list_expenses(db: Session = Depends(get_db)) -> list[ExpenseRead]:
    """Return all persisted Expenses.

    See docs/architecture.md's Expense contract and "Established API
    decisions" for the response shape and wire-format guarantees.
    """
    return db.execute(select(Expense).order_by(Expense.id)).scalars().all()
