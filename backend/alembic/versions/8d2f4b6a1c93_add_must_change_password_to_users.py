"""add must_change_password to users

Revision ID: 8d2f4b6a1c93
Revises: 5c3e9a1d7f20
Create Date: 2026-11-23 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8d2f4b6a1c93'
down_revision: str | Sequence[str] | None = '5c3e9a1d7f20'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default: the existing users do not have to change their password
    op.add_column(
        'users',
        sa.Column(
            'must_change_password', sa.Boolean(), server_default='0', nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'must_change_password')
