"""SQLAlchemy models for users, their login sessions, and their expenses.

See docs/architecture.md ("The walking-skeleton Expense contract") for the
accepted field meanings and invariants the Expense model must preserve.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.categorize import CATEGORIES
from app.database import Base

_CATEGORY_LIST_SQL = ", ".join(f"'{category}'" for category in CATEGORIES)


class User(Base):
    """A person who can log in. Every Expense and PlaidItem belongs to one.

    email is stored lowercased (enforced by the check constraint below), so
    the plain unique constraint is also case-insensitive: "Dave@x.com" and
    "dave@x.com" can't both sign up. password_hash is an Argon2id hash from
    app/auth.py -- the plaintext password is never stored.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )


class UserSession(Base):
    """One logged-in session, created at login and deleted at logout.

    Only a SHA-256 hash of the session token is stored. The token itself is
    handed to the client once and never kept, so someone who can read this
    table still can't use the sessions in it.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_sessions_user_id_users", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("token_hash", name="uq_sessions_token_hash"),)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_expenses_user_id_users"), nullable=False, index=True
    )
    merchant: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    # No precision/scale: PostgreSQL NUMERIC(p, s) would silently round a value
    # with more than s decimal places instead of rejecting it. Excess precision
    # is rejected instead via the scale() check below.
    amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    # Null means "no guess was made": either a caller supplied category
    # explicitly (POST with category set, or any PATCH that sets category),
    # so there's no classifier confidence to report. Set by the baseline
    # classifier (see app/categorize.py) whenever it's the one picking the
    # category instead.
    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    # Only set for expenses imported via Plaid sync; lets a later sync look
    # a transaction up to dedupe it, apply a Plaid-side edit, or delete it.
    plaid_transaction_id: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "scale(amount) <= 2", name="ck_expenses_amount_max_two_decimal_places"
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_expenses_confidence_range",
        ),
        CheckConstraint(
            "char_length(trim(merchant)) > 0", name="ck_expenses_merchant_not_blank"
        ),
        CheckConstraint(
            "char_length(trim(description)) > 0",
            name="ck_expenses_description_not_blank",
        ),
        CheckConstraint(
            f"category IN ({_CATEGORY_LIST_SQL})", name="ck_expenses_category_allowed"
        ),
        # Named explicitly (rather than mapped_column(unique=True), which
        # leaves Postgres to pick its own default name) so this matches the
        # name the migration gives the same constraint -- Base has no
        # naming convention, so the two would otherwise diverge and alembic
        # autogenerate would see a phantom difference.
        UniqueConstraint(
            "plaid_transaction_id", name="uq_expenses_plaid_transaction_id"
        ),
    )


class PlaidItem(Base):
    """One linked bank connection ("Item", in Plaid's terms).

    access_token is the credential Plaid's API itself requires on every
    later call for this connection -- there is no way around storing it.
    cursor tracks transactions_sync's position so a later sync only pulls
    what's new instead of re-fetching everything.
    """

    __tablename__ = "plaid_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_plaid_items_user_id_users"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    cursor: Mapped[str | None] = mapped_column(String, nullable=True)
