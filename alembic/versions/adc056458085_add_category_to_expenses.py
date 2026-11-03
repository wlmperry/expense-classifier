"""add category to expenses

Revision ID: adc056458085
Revises: f18c7f08b049
Create Date: 2026-11-02 14:53:46.466046

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'adc056458085'
down_revision: str | Sequence[str] | None = 'f18c7f08b049'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills every existing row to 'Other' as part of
    # adding the column, in one statement, instead of a separate UPDATE.
    op.add_column(
        'expenses',
        sa.Column('category', sa.String(), nullable=False, server_default='Other'),
    )
    # Drop the default once existing rows are backfilled: every row from
    # here on must say its category explicitly (the API itself still fills
    # in a value via the classifier when a client omits it).
    op.alter_column('expenses', 'category', server_default=None)
    op.create_check_constraint(
        'ck_expenses_category_allowed',
        'expenses',
        "category IN ('Food & Dining', 'Transportation', 'Housing & Utilities', "
        "'Shopping', 'Entertainment', 'Health & Fitness', 'Other')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_expenses_category_allowed', 'expenses', type_='check')
    op.drop_column('expenses', 'category')
