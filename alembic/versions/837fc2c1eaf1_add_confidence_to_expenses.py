"""add confidence to expenses

Revision ID: 837fc2c1eaf1
Revises: ce329f18d717
Create Date: 2026-11-08 16:17:21.125994

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '837fc2c1eaf1'
down_revision: str | Sequence[str] | None = 'ce329f18d717'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('expenses', sa.Column('confidence', sa.Numeric(), nullable=True))
    op.create_check_constraint(
        'ck_expenses_confidence_range',
        'expenses',
        'confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_expenses_confidence_range', 'expenses', type_='check')
    op.drop_column('expenses', 'confidence')
