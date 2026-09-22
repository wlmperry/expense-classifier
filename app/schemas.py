"""Pydantic schemas for the API boundary.

See docs/architecture.md ("The walking-skeleton Expense contract") for the
field meanings and the `amount` / `expense_date` wire-format rules this
schema must preserve.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ExpenseRead(BaseModel):
    """The persisted Expense shape returned across the API boundary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant: str
    description: str
    amount: Decimal
    expense_date: date
