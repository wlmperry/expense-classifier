"""SQLAlchemy models for the walking-skeleton Expense contract.

See docs/architecture.md ("The walking-skeleton Expense contract") for the
accepted field meanings and invariants this model must preserve.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.categorize import CATEGORIES
from app.database import Base

_CATEGORY_LIST_SQL = ", ".join(f"'{category}'" for category in CATEGORIES)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    # No precision/scale: PostgreSQL NUMERIC(p, s) would silently round a value
    # with more than s decimal places instead of rejecting it. Excess precision
    # is rejected instead via the scale() check below.
    amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "scale(amount) <= 2", name="ck_expenses_amount_max_two_decimal_places"
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
    item_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    cursor: Mapped[str | None] = mapped_column(String, nullable=True)
