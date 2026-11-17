"""add user_id to meetings

Revision ID: 06d5d9a19ef4
Revises: 2fa7e726114c
Create Date: 2026-11-16 15:35:41.863621

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '06d5d9a19ef4'
down_revision: str | Sequence[str] | None = '2fa7e726114c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOREIGN_KEY = 'fk_meetings_user_id_users'


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    # The existing meetings are given to the admin. The check runs before any
    # change to the table: MySQL cannot roll back ALTER TABLE, so stopping
    # after add_column would leave the column behind, and running the
    # migration again would then fail.
    admin_id = None
    meeting_count = connection.scalar(sa.text('SELECT COUNT(*) FROM meetings'))
    if meeting_count:
        admin_id = connection.scalar(
            sa.text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
        )
        if admin_id is None:
            raise RuntimeError(
                'Meetings exist but there is no admin yet to own them. '
                'Create the admin first (python -m app.create_admin), '
                'then run the migration again.'
            )

    # Nullable at first: the existing rows have no owner until the UPDATE
    op.add_column('meetings', sa.Column('user_id', sa.Integer(), nullable=True))
    if admin_id is not None:
        connection.execute(
            sa.text('UPDATE meetings SET user_id = :admin_id'),
            {'admin_id': admin_id},
        )
    op.alter_column(
        'meetings', 'user_id', existing_type=sa.Integer(), nullable=False
    )
    # MySQL adds an index for the foreign key by itself
    op.create_foreign_key(FOREIGN_KEY, 'meetings', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FOREIGN_KEY, 'meetings', type_='foreignkey')
    op.drop_column('meetings', 'user_id')
