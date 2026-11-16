"""add category source to expenses

Revision ID: 0254b9b63975
Revises: 8c5fbee890de
Create Date: 2026-11-16

Records which step categorized an expense, "rules" or "model" (Issue #55),
so the UI can show whether the ML classifier was involved.

Every existing row with a confidence score was categorized automatically
before the ML model existed, so by the keyword rules -- except "Other": an
expense no rule matched was stored as ("Other", 0.2), and the new code
stores that same situation with no source. So rows with a confidence score
are backfilled with "rules" unless their category is Other (no keyword rule
ever returns Other). Rows without a confidence score stay null: their
category isn't an automatic guess.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0254b9b63975'
down_revision: str | Sequence[str] | None = '8c5fbee890de'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('expenses', sa.Column('category_source', sa.String(), nullable=True))
    op.create_check_constraint(
        'ck_expenses_category_source_allowed',
        'expenses',
        "category_source IS NULL OR category_source IN ('rules', 'model')",
    )
    op.execute(
        "UPDATE expenses SET category_source = 'rules' "
        "WHERE confidence IS NOT NULL AND category <> 'Other'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_expenses_category_source_allowed', 'expenses', type_='check')
    op.drop_column('expenses', 'category_source')
