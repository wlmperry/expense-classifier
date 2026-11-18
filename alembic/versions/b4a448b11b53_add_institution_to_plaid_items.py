"""add institution to plaid items

Revision ID: b4a448b11b53
Revises: 0254b9b63975
Create Date: 2026-11-17

Records which bank each linked Item is (Issue #60), so a user can link
several banks but not the same bank twice. Both columns are nullable:
Items linked before this migration have no institution saved, and the
backend fills them in from Plaid's /item/get the first time it needs them.
A migration can't call Plaid, so there is no backfill here.

The unique constraint on (user_id, institution_id) allows any number of
rows with a null institution_id, because Postgres treats nulls as distinct.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4a448b11b53'
down_revision: str | Sequence[str] | None = '0254b9b63975'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('plaid_items', sa.Column('institution_id', sa.String(), nullable=True))
    op.add_column('plaid_items', sa.Column('institution_name', sa.String(), nullable=True))
    op.create_unique_constraint(
        'uq_plaid_items_user_id_institution_id',
        'plaid_items',
        ['user_id', 'institution_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_plaid_items_user_id_institution_id', 'plaid_items', type_='unique')
    op.drop_column('plaid_items', 'institution_name')
    op.drop_column('plaid_items', 'institution_id')
