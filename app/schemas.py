"""Pydantic schemas for the API boundary.

See docs/architecture.md ("The walking-skeleton Expense contract") for the
field meanings and the `amount` / `expense_date` wire-format rules this
schema must preserve.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.categorize import CATEGORIES

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
CategoryLiteral = Literal[CATEGORIES]  # type: ignore[valid-type]


def _require_decimal_string(v: object) -> object:
    """Shared `amount` "before" validator body for ExpenseCreate/ExpenseUpdate:
    reject anything that isn't a decimal string, e.g. "12.34". Null-handling
    differs between the two callers, so that check stays with each caller."""
    if not isinstance(v, str):
        # ValueError, not TypeError: Pydantic validators must raise
        # ValueError/AssertionError to produce a normal 422 response --
        # TypeError propagates as an unhandled 500 instead.
        raise ValueError("amount must be a decimal string, e.g. \"12.34\"")  # noqa: TRY004
    return v


def _require_scale_at_most_two(v: Decimal) -> Decimal:
    """Shared `amount` "after" validator body: reject more than two decimal
    places (matches the database's `scale(amount) <= 2` check constraint)."""
    exponent = v.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise ValueError("amount must have no more than two decimal places")
    return v


def _require_iso_date_string(v: object) -> object:
    """Shared `expense_date` "before" validator body: reject anything that
    isn't an exact `YYYY-MM-DD` string. Null-handling differs between
    ExpenseCreate and ExpenseUpdate, so that check stays with each caller."""
    if not isinstance(v, str) or not _ISO_DATE_RE.fullmatch(v):
        raise ValueError("expense_date must be an ISO 8601 date string (YYYY-MM-DD)")
    return v


class ExpenseRead(BaseModel):
    """The persisted Expense shape returned across the API boundary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant: str
    description: str
    amount: Decimal
    expense_date: date
    category: str
    # Null means category wasn't auto-classified -- either a caller supplied
    # it directly, or a PATCH changed it, so there's no classifier guess
    # to score. Never settable by a client: see app/categorize.py.
    confidence: Decimal | None


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
        return _require_decimal_string(v)

    @field_validator("amount", mode="after")
    @classmethod
    def amount_scale_must_not_exceed_two(cls, v: Decimal) -> Decimal:
        return _require_scale_at_most_two(v)

    @field_validator("expense_date", mode="before")
    @classmethod
    def expense_date_must_be_iso_string(cls, v: object) -> object:
        return _require_iso_date_string(v)


class ExpenseUpdate(BaseModel):
    """The partial-update shape accepted by PATCH /expenses/{id}.

    Every field is optional -- only a field present in the request body is
    changed; an omitted field keeps its current persisted value. Unlike
    ExpenseCreate, an omitted category is *not* re-derived from the
    classifier here: "omitted" means "leave it alone," not "guess for me."
    A field sent explicitly as null is rejected, since none of these
    columns are nullable in the database.
    """

    model_config = ConfigDict(extra="forbid")

    merchant: str | None = None
    description: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    expense_date: date | None = None
    category: CategoryLiteral | None = None

    @field_validator("merchant", "description", mode="before")
    @classmethod
    def reject_null_or_blank(cls, v: object) -> object:
        if v is None:
            raise ValueError("must not be null")
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_be_non_null_string(cls, v: object) -> object:
        if v is None:
            raise ValueError("amount must not be null")
        return _require_decimal_string(v)

    @field_validator("amount", mode="after")
    @classmethod
    def amount_scale_must_not_exceed_two(cls, v: Decimal) -> Decimal:
        return _require_scale_at_most_two(v)

    @field_validator("expense_date", mode="before")
    @classmethod
    def expense_date_must_be_non_null_iso_string(cls, v: object) -> object:
        if v is None:
            raise ValueError("expense_date must not be null")
        return _require_iso_date_string(v)

    @field_validator("category", mode="before")
    @classmethod
    def category_must_not_be_null(cls, v: object) -> object:
        if v is None:
            raise ValueError("category must not be null")
        return v

    @model_validator(mode="after")
    def at_least_one_field_given(self) -> "ExpenseUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


# Deliberately loose: one "@" with something on both sides and a dot in the
# domain. Fully validating email syntax would need the email-validator
# package; the real proof an address works is email verification, which is
# planned as a later Issue.
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# The longest address the email standards allow.
_EMAIL_MAX_LENGTH = 254
# Argon2id handles long input fine; the cap just stops a multi-megabyte
# "password" from being sent to the hasher.
_PASSWORD_MAX_LENGTH = 128


class LoginRequest(BaseModel):
    """Email and password sent to POST /auth/login.

    email is trimmed and lowercased here, so every lookup and insert sees
    the same form. Login only requires a non-empty password: a too-short
    one simply won't match, which gives the same "Invalid email or
    password" answer as any other wrong password.
    """

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=1, max_length=_PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > _EMAIL_MAX_LENGTH or not _EMAIL_RE.fullmatch(v):
            raise ValueError("must be a valid email address")
        return v


class RegisterRequest(LoginRequest):
    """Same as LoginRequest, plus the minimum length a new password needs."""

    password: str = Field(min_length=8, max_length=_PASSWORD_MAX_LENGTH)


class UserRead(BaseModel):
    """The public view of a user. Never includes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class AuthResponse(BaseModel):
    """Returned by register and login. token goes in later requests'
    Authorization header as `Bearer <token>`."""

    token: str
    user: UserRead


class PlaidItemStatusResponse(BaseModel):
    """Whether the current user already has a bank linked.

    item_id is None when no Item has ever been linked.
    """

    item_id: str | None


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
