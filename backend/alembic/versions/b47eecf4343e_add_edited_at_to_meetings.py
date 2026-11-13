"""add edited_at to meetings

Revision ID: b47eecf4343e
Revises: 0c1714bac68d
Create Date: 2026-11-13 19:24:41.273237

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b47eecf4343e'
down_revision: str | Sequence[str] | None = '0c1714bac68d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: the existing meetings have never been edited
    op.add_column('meetings', sa.Column('edited_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('meetings', 'edited_at')
