"""add plaid transaction id to expenses

Revision ID: ce329f18d717
Revises: 391bc80a5267
Create Date: 2026-11-07 09:49:09.009283

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ce329f18d717'
down_revision: str | Sequence[str] | None = '391bc80a5267'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: only expenses imported via Plaid sync carry this; manually
    # entered expenses never have one. Unique so the sync endpoint can look
    # an incoming transaction up by it to dedupe/modify/remove correctly.
    op.add_column(
        'expenses', sa.Column('plaid_transaction_id', sa.String(), nullable=True)
    )
    op.create_unique_constraint(
        'uq_expenses_plaid_transaction_id', 'expenses', ['plaid_transaction_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_expenses_plaid_transaction_id', 'expenses', type_='unique')
    op.drop_column('expenses', 'plaid_transaction_id')
