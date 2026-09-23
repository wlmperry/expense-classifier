"""Pydantic schemas for the API boundary.

See docs/architecture.md ("The walking-skeleton Expense contract") for the
field meanings and the `amount` / `expense_date` wire-format rules this
schema must preserve.
"""

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class ExpenseRead(BaseModel):
    """The persisted Expense shape returned across the API boundary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant: str
    description: str
    amount: Decimal
    expense_date: date


class ExpenseCreate(BaseModel):
    """The Expense creation shape accepted across the API boundary."""

    model_config = ConfigDict(extra="forbid")

    merchant: str
    description: str
    amount: Decimal = Field(gt=0)
    expense_date: date

    @field_validator("merchant", "description")
    @classmethod
    def reject_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_be_string(cls, v: object) -> object:
        if not isinstance(v, str):
            # ValueError, not TypeError: Pydantic validators must raise
            # ValueError/AssertionError to produce a normal 422 response --
            # TypeError propagates as an unhandled 500 instead.
            raise ValueError("amount must be a decimal string, e.g. \"12.34\"")  # noqa: TRY004
        return v

    @field_validator("amount", mode="after")
    @classmethod
    def amount_scale_must_not_exceed_two(cls, v: Decimal) -> Decimal:
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("amount must have no more than two decimal places")
        return v

    @field_validator("expense_date", mode="before")
    @classmethod
    def expense_date_must_be_iso_string(cls, v: object) -> object:
        if not isinstance(v, str) or not _ISO_DATE_RE.fullmatch(v):
            raise ValueError("expense_date must be an ISO 8601 date string (YYYY-MM-DD)")
        return v
