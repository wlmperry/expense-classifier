"""Pydantic schemas for the API boundary.

See docs/architecture.md ("The walking-skeleton Expense contract") for the
field meanings and the `amount` / `expense_date` wire-format rules this
schema must preserve.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.categorize import CATEGORIES

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
CategoryLiteral = Literal[CATEGORIES]  # type: ignore[valid-type]


class ExpenseRead(BaseModel):
    """The persisted Expense shape returned across the API boundary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant: str
    description: str
    amount: Decimal
    expense_date: date
    category: str


class ExpenseCreate(BaseModel):
    """The Expense creation shape accepted across the API boundary.

    category is optional: if the client doesn't supply one, the API runs
    the baseline classifier (see app/categorize.py) on merchant/description
    instead of rejecting the request. A client that already knows the
    category -- a human picking from a dropdown, for instance -- can always
    supply it directly and skip the guess.
    """

    model_config = ConfigDict(extra="forbid")

    merchant: str
    description: str
    amount: Decimal = Field(gt=0)
    expense_date: date
    category: CategoryLiteral | None = None

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


class PlaidLinkTokenResponse(BaseModel):
    """What the frontend needs to open Plaid Link."""

    link_token: str
    expiration: datetime


class PlaidSandboxPublicTokenResponse(BaseModel):
    """Sandbox-only helper: stands in for what Link would return after a
    real user finished linking a bank."""

    public_token: str


class PlaidExchangePublicTokenRequest(BaseModel):
    """public_token comes from Link (or the sandbox helper above) and is
    only valid for a few minutes -- it must be exchanged for a durable
    access_token right away."""

    model_config = ConfigDict(extra="forbid")

    public_token: str


class PlaidExchangePublicTokenResponse(BaseModel):
    item_id: str


class PlaidSyncResponse(BaseModel):
    """What changed on this sync: how many new Expenses were created, and
    the Expenses themselves, each already categorized."""

    added_count: int
    added: list[ExpenseRead]
