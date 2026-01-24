"""add_users_table

Revision ID: c8f92183a4d1
Revises: b5e75071025f
Create Date: 2026-01-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f92183a4d1'
down_revision: Union[str, Sequence[str], None] = 'b5e75071025f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users table and add user_id to research_tasks."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('image', sa.Text(), nullable=True),
        sa.Column('google_id', sa.String(255), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for users table
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_google_id', 'users', ['google_id'])

    # Add user_id column to research_tasks
    op.add_column(
        'research_tasks',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('ix_research_tasks_user_id', 'research_tasks', ['user_id'])


def downgrade() -> None:
    """Drop users table and remove user_id from research_tasks."""
    op.drop_index('ix_research_tasks_user_id', 'research_tasks')
    op.drop_column('research_tasks', 'user_id')

    op.drop_index('ix_users_google_id', 'users')
    op.drop_index('ix_users_email', 'users')
    op.drop_table('users')
