"""replace summary with interview insights

Revision ID: 0c1714bac68d
Revises: ee66e83a2b41
Create Date: 2026-11-12 23:15:46.234658

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0c1714bac68d'
down_revision: str | Sequence[str] | None = 'ee66e83a2b41'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Written here, not imported from the app: a migration must keep working the
# same way after the app's code changes
OLD_FORMAT_MESSAGE = (
    "This interview was processed with an older summary format. Process it again."
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('meetings', sa.Column('interviewee', sa.JSON(), nullable=True))
    op.add_column('meetings', sa.Column('insights', sa.JSON(), nullable=True))

    # The old summary is deleted below, so a processed meeting would be left
    # with no summary at all. Marked as failed, it shows the "Try again" button
    # that processes it again in the new format
    op.execute(
        sa.text(
            "UPDATE meetings SET status = 'failed', error_message = :message "
            "WHERE status = 'done'"
        ).bindparams(message=OLD_FORMAT_MESSAGE)
    )

    op.drop_column('meetings', 'summary')
    op.drop_column('meetings', 'key_topics')
    # Dropping the table removes its index too; drop_index first would fail on
    # MySQL, because the foreign key needs it (see the first migration)
    op.drop_table('action_items')


def downgrade() -> None:
    """Downgrade schema.

    Brings back the old columns and table, but not their data: it was deleted
    by the upgrade. The meetings marked as failed by the upgrade stay failed.
    """
    op.create_table('action_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meeting_id', sa.Integer(), nullable=False),
    sa.Column('assignee', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_action_items_meeting_id'), 'action_items', ['meeting_id'], unique=False)
    op.add_column('meetings', sa.Column('key_topics', sa.JSON(), nullable=True))
    op.add_column('meetings', sa.Column('summary', sa.Text(), nullable=True))
    op.drop_column('meetings', 'insights')
    op.drop_column('meetings', 'interviewee')
