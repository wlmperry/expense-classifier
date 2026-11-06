"""add plaid_items table

Revision ID: 391bc80a5267
Revises: adc056458085
Create Date: 2026-11-02 15:01:47.719748

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '391bc80a5267'
down_revision: str | Sequence[str] | None = 'adc056458085'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'plaid_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.String(), nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('cursor', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('item_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('plaid_items')
