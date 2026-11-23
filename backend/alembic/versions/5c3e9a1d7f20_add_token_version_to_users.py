"""add token_version to users

Revision ID: 5c3e9a1d7f20
Revises: 06d5d9a19ef4
Create Date: 2026-11-23 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5c3e9a1d7f20'
down_revision: str | Sequence[str] | None = '06d5d9a19ef4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default: the existing users start at version 0
    op.add_column(
        'users',
        sa.Column('token_version', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'token_version')
