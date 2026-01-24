"""initial_research_tables

Revision ID: b5e75071025f
Revises:
Create Date: 2026-01-13 23:23:45.049064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e75071025f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create research tables."""
    # Research tasks table
    op.create_table(
        'research_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('depth', sa.String(20), server_default='standard'),
        sa.Column('scenario', sa.String(20), server_default='academic'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('report', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Research steps table
    op.create_table(
        'research_steps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('research_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Research sources table
    op.create_table(
        'research_sources',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('research_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index('ix_research_tasks_status', 'research_tasks', ['status'])
    op.create_index('ix_research_tasks_created_at', 'research_tasks', ['created_at'])
    op.create_index('ix_research_steps_task_id', 'research_steps', ['task_id'])
    op.create_index('ix_research_sources_task_id', 'research_sources', ['task_id'])


def downgrade() -> None:
    """Drop research tables."""
    op.drop_index('ix_research_sources_task_id', 'research_sources')
    op.drop_index('ix_research_steps_task_id', 'research_steps')
    op.drop_index('ix_research_tasks_created_at', 'research_tasks')
    op.drop_index('ix_research_tasks_status', 'research_tasks')

    op.drop_table('research_sources')
    op.drop_table('research_steps')
    op.drop_table('research_tasks')
