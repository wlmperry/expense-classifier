"""add users and sessions

Revision ID: 8c5fbee890de
Revises: 3c86f19d4985
Create Date: 2026-11-15 19:07:47.518651

Adds real user accounts (Issue #44). Every expense and Plaid item now
belongs to a user, so the existing rows need an owner before user_id can
be made required. This migration therefore runs in three phases:

  1. Create users and sessions, and add user_id to expenses and
     plaid_items as NULLable.
  2. Create the demo@example.com user and assign every existing row to it.
  3. Make user_id NOT NULL and add its foreign keys.

The demo user's password is a hash of a random value that is thrown away
immediately, so nobody can log in as demo until someone runs
scripts/set_password.py (see docs/development.md). pwdlib is imported
directly rather than through app/auth.py, so this migration keeps working
if app/auth.py changes later.

Downgrading drops the users and sessions tables and every expense's owner.
The expenses themselves are kept.
"""
import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from pwdlib import PasswordHash

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8c5fbee890de'
down_revision: str | Sequence[str] | None = '3c86f19d4985'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_EMAIL = "demo@example.com"


def upgrade() -> None:
    """Upgrade schema."""
    # Phase 1: new tables, and nullable user_id columns.
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('email = lower(email)', name='ck_users_email_lowercase'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_sessions_user_id_users', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_sessions_token_hash'),
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.add_column('expenses', sa.Column('user_id', sa.Integer(), nullable=True))
    op.add_column('plaid_items', sa.Column('user_id', sa.Integer(), nullable=True))

    # Phase 2: a demo user owns everything that existed before accounts did.
    unusable_password_hash = PasswordHash.recommended().hash(secrets.token_urlsafe(32))
    demo_user_id = op.get_bind().execute(
        sa.text(
            "INSERT INTO users (email, password_hash) VALUES (:email, :password_hash) RETURNING id"
        ),
        {"email": DEMO_EMAIL, "password_hash": unusable_password_hash},
    ).scalar_one()
    op.execute(sa.text("UPDATE expenses SET user_id = :id").bindparams(id=demo_user_id))
    op.execute(sa.text("UPDATE plaid_items SET user_id = :id").bindparams(id=demo_user_id))

    # Phase 3: now that every row has an owner, require one.
    op.alter_column('expenses', 'user_id', nullable=False)
    op.create_index(op.f('ix_expenses_user_id'), 'expenses', ['user_id'], unique=False)
    op.create_foreign_key('fk_expenses_user_id_users', 'expenses', 'users', ['user_id'], ['id'])
    op.alter_column('plaid_items', 'user_id', nullable=False)
    op.create_index(op.f('ix_plaid_items_user_id'), 'plaid_items', ['user_id'], unique=False)
    op.create_foreign_key('fk_plaid_items_user_id_users', 'plaid_items', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_plaid_items_user_id_users', 'plaid_items', type_='foreignkey')
    op.drop_index(op.f('ix_plaid_items_user_id'), table_name='plaid_items')
    op.drop_column('plaid_items', 'user_id')
    op.drop_constraint('fk_expenses_user_id_users', 'expenses', type_='foreignkey')
    op.drop_index(op.f('ix_expenses_user_id'), table_name='expenses')
    op.drop_column('expenses', 'user_id')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_table('users')
