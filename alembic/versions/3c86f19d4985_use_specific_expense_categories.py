"""use specific expense categories

Revision ID: 3c86f19d4985
Revises: 837fc2c1eaf1
Create Date: 2026-11-13 19:28:19.094350

Replaces the 7 broad categories with 20 specific ones (Issue #50). The
category check constraint has to be dropped before any row is converted,
since the old constraint rejects every new name, and recreated afterward
with the new list.

Both lists are copied into this file rather than imported from
app/categorize.py on purpose: a migration describes one fixed step in the
database's history, so it must keep doing the same thing even after
CATEGORIES changes again in some later Issue.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.categorize import classify_with_confidence

# revision identifiers, used by Alembic.
revision: str = '3c86f19d4985'
down_revision: str | Sequence[str] | None = '837fc2c1eaf1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CATEGORIES: tuple[str, ...] = (
    "Food & Dining",
    "Transportation",
    "Housing & Utilities",
    "Shopping",
    "Entertainment",
    "Health & Fitness",
    "Other",
)

# Each new category's old parent. Used by downgrade(), and its keys are the
# new allowed list.
NEW_TO_OLD: dict[str, str] = {
    "Groceries": "Food & Dining",
    "Restaurants & Bars": "Food & Dining",
    "Coffee Shops": "Food & Dining",
    "Food Delivery": "Food & Dining",
    "Gas & Fuel": "Transportation",
    "Rideshare & Transit": "Transportation",
    "Travel": "Transportation",
    "Rent & Mortgage": "Housing & Utilities",
    "Utilities": "Housing & Utilities",
    "Online Shopping": "Shopping",
    "General Merchandise": "Shopping",
    "Electronics": "Shopping",
    "Clothing": "Shopping",
    "Streaming & Subscriptions": "Entertainment",
    "Movies & Events": "Entertainment",
    "Gaming": "Entertainment",
    "Pharmacy": "Health & Fitness",
    "Gym & Fitness": "Health & Fitness",
    "Medical": "Health & Fitness",
    "Other": "Other",
}
NEW_CATEGORIES: tuple[str, ...] = tuple(NEW_TO_OLD)

# Where a human-chosen old category goes. A person picked the broad group,
# so the row keeps that group; the specific name within it is a fixed
# default because there's no way to know which one they meant.
OLD_TO_NEW_DEFAULT: dict[str, str] = {
    "Food & Dining": "Restaurants & Bars",
    "Transportation": "Rideshare & Transit",
    "Housing & Utilities": "Utilities",
    "Shopping": "General Merchandise",
    "Entertainment": "Movies & Events",
    "Health & Fitness": "Medical",
    "Other": "Other",
}


def _allowed_categories_sql(categories: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{category}'" for category in categories)
    return f"category IN ({quoted})"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('ck_expenses_category_allowed', 'expenses', type_='check')

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, merchant, description, category, confidence FROM expenses")
    ).all()

    for row in rows:
        # Non-null confidence means the classifier picked this category, not
        # a person, so it's safe to let the new rules re-guess it. A
        # human-chosen row (null confidence) is never re-guessed.
        if row.confidence is not None:
            category, confidence = classify_with_confidence(row.merchant, row.description)
        else:
            category, confidence = OLD_TO_NEW_DEFAULT[row.category], None

        # The classifier is imported live, so a later Issue that renames
        # categories again could make it return a name this migration's
        # constraint doesn't allow. Fall back to the fixed mapping then, with
        # no confidence, since the result is no longer the classifier's guess.
        if category not in NEW_CATEGORIES:
            category, confidence = OLD_TO_NEW_DEFAULT[row.category], None

        connection.execute(
            sa.text(
                "UPDATE expenses SET category = :category, confidence = :confidence "
                "WHERE id = :id"
            ),
            {"category": category, "confidence": confidence, "id": row.id},
        )

    op.create_check_constraint(
        'ck_expenses_category_allowed',
        'expenses',
        _allowed_categories_sql(NEW_CATEGORIES),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_expenses_category_allowed', 'expenses', type_='check')

    connection = op.get_bind()
    for new_category, old_category in NEW_TO_OLD.items():
        connection.execute(
            sa.text("UPDATE expenses SET category = :old WHERE category = :new"),
            {"old": old_category, "new": new_category},
        )

    op.create_check_constraint(
        'ck_expenses_category_allowed',
        'expenses',
        _allowed_categories_sql(OLD_CATEGORIES),
    )
