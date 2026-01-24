"""Add skills tables

Revision ID: d908fb77cf42
Revises: drop_filename
Create Date: 2026-01-22 09:49:24.781297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd908fb77cf42'
down_revision: Union[str, Sequence[str], None] = 'drop_filename'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create skill_definitions table
    op.create_table(
        'skill_definitions',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('module_path', sa.String(length=500), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=False),
        sa.Column('source_code', sa.Text(), nullable=True),
        sa.Column('source_code_hash', sa.String(length=64), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('author', sa.String(length=255), nullable=False, server_default='hyperagent'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('invocation_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('last_invoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_skill_definitions_category'), 'skill_definitions', ['category'], unique=False)
    op.create_index(op.f('ix_skill_definitions_enabled'), 'skill_definitions', ['enabled'], unique=False)

    # Create skill_executions table
    op.create_table(
        'skill_executions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('skill_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('input_params', sa.Text(), nullable=False),
        sa.Column('output_data', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('agent_type', sa.String(length=50), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skill_definitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_skill_executions_skill_id'), 'skill_executions', ['skill_id'], unique=False)
    op.create_index(op.f('ix_skill_executions_user_id'), 'skill_executions', ['user_id'], unique=False)
    op.create_index(op.f('ix_skill_executions_status'), 'skill_executions', ['status'], unique=False)
    op.create_index('ix_skill_executions_user_status', 'skill_executions', ['user_id', 'status'], unique=False)
    op.create_index('ix_skill_executions_skill_status', 'skill_executions', ['skill_id', 'status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_skill_executions_skill_status', table_name='skill_executions')
    op.drop_index('ix_skill_executions_user_status', table_name='skill_executions')
    op.drop_index(op.f('ix_skill_executions_status'), table_name='skill_executions')
    op.drop_index(op.f('ix_skill_executions_user_id'), table_name='skill_executions')
    op.drop_index(op.f('ix_skill_executions_skill_id'), table_name='skill_executions')
    op.drop_table('skill_executions')
    op.drop_index(op.f('ix_skill_definitions_enabled'), table_name='skill_definitions')
    op.drop_index(op.f('ix_skill_definitions_category'), table_name='skill_definitions')
    op.drop_table('skill_definitions')
