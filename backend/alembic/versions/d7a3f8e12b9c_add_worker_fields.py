"""add_worker_fields

Revision ID: d7a3f8e12b9c
Revises: c8f92183a4d1
Create Date: 2026-01-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a3f8e12b9c'
down_revision: Union[str, Sequence[str], None] = 'c8f92183a4d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add worker tracking fields to research_tasks and create background_tasks table."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if columns exist before adding them to research_tasks
    existing_columns = {col['name'] for col in inspector.get_columns('research_tasks')}

    if 'worker_job_id' not in existing_columns:
        op.add_column('research_tasks', sa.Column('worker_job_id', sa.String(64), nullable=True))
    if 'worker_name' not in existing_columns:
        op.add_column('research_tasks', sa.Column('worker_name', sa.String(100), nullable=True))
    if 'started_at' not in existing_columns:
        op.add_column('research_tasks', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    if 'progress' not in existing_columns:
        op.add_column('research_tasks', sa.Column('progress', sa.Integer(), server_default='0', nullable=False))
    if 'retry_count' not in existing_columns:
        op.add_column('research_tasks', sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False))
    if 'priority' not in existing_columns:
        op.add_column('research_tasks', sa.Column('priority', sa.Integer(), server_default='0', nullable=False))

    # Check if indexes exist before creating them
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('research_tasks')}

    if 'ix_research_tasks_worker_job_id' not in existing_indexes:
        op.create_index('ix_research_tasks_worker_job_id', 'research_tasks', ['worker_job_id'])
    if 'ix_research_tasks_status' not in existing_indexes:
        op.create_index('ix_research_tasks_status', 'research_tasks', ['status'])

    # Check if background_tasks table exists before creating it
    if 'background_tasks' not in inspector.get_table_names():
        op.create_table(
            'background_tasks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('task_type', sa.String(50), nullable=False),
            sa.Column('status', sa.String(20), server_default='pending', nullable=False),
            sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
            sa.Column('payload', sa.Text(), nullable=True),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('worker_job_id', sa.String(64), nullable=True),
            sa.Column('worker_name', sa.String(100), nullable=True),
            sa.Column('progress', sa.Integer(), server_default='0', nullable=False),
            sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )

        # Create indexes for background_tasks (only if table was created)
        op.create_index('ix_background_tasks_task_type', 'background_tasks', ['task_type'])
        op.create_index('ix_background_tasks_status', 'background_tasks', ['status'])
        op.create_index('ix_background_tasks_worker_job_id', 'background_tasks', ['worker_job_id'])
        op.create_index('ix_background_tasks_user_id', 'background_tasks', ['user_id'])


def downgrade() -> None:
    """Remove worker tracking fields and drop background_tasks table."""
    # Drop background_tasks table
    op.drop_index('ix_background_tasks_user_id', 'background_tasks')
    op.drop_index('ix_background_tasks_worker_job_id', 'background_tasks')
    op.drop_index('ix_background_tasks_status', 'background_tasks')
    op.drop_index('ix_background_tasks_task_type', 'background_tasks')
    op.drop_table('background_tasks')

    # Remove worker fields from research_tasks
    op.drop_index('ix_research_tasks_status', 'research_tasks')
    op.drop_index('ix_research_tasks_worker_job_id', 'research_tasks')
    op.drop_column('research_tasks', 'priority')
    op.drop_column('research_tasks', 'retry_count')
    op.drop_column('research_tasks', 'progress')
    op.drop_column('research_tasks', 'started_at')
    op.drop_column('research_tasks', 'worker_name')
    op.drop_column('research_tasks', 'worker_job_id')
