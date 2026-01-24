"""add_user_id_to_research_tasks

Revision ID: e367d61b6157
Revises: d7a3f8e12b9c
Create Date: 2026-01-14 12:11:00.792928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e367d61b6157'
down_revision: Union[str, Sequence[str], None] = 'd7a3f8e12b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_id column to research_tasks as required field."""
    # Delete any existing research tasks (development only - no user association yet)
    op.execute("DELETE FROM research_tasks")

    # Add user_id column as NOT NULL
    op.add_column(
        'research_tasks',
        sa.Column('user_id', sa.String(36), nullable=False)
    )

    # Create foreign key constraint with CASCADE delete
    op.create_foreign_key(
        'research_tasks_user_id_fkey',
        'research_tasks',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create index on user_id
    op.create_index('ix_research_tasks_user_id', 'research_tasks', ['user_id'])


def downgrade() -> None:
    """Remove user_id column from research_tasks."""
    op.drop_index('ix_research_tasks_user_id', 'research_tasks')
    op.drop_constraint('research_tasks_user_id_fkey', 'research_tasks', type_='foreignkey')
    op.drop_column('research_tasks', 'user_id')
