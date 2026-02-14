"""Add projects table

Revision ID: add_projects
Revises: d908fb77cf42
Create Date: 2026-02-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision: str = 'add_projects'
down_revision: Union[str, Sequence[str], None] = 'd908fb77cf42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists (handles dev auto-create)."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists on a table."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def _fk_exists(table_name: str, fk_name: str) -> bool:
    """Check if a foreign key constraint exists."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    fks = inspector.get_foreign_keys(table_name)
    return any(fk.get("name") == fk_name for fk in fks)


def upgrade() -> None:
    """Upgrade schema."""
    # Create projects table (skip if auto-created by dev mode)
    if not _table_exists('projects'):
        op.create_table(
            'projects',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('color', sa.String(length=20), nullable=True),
            sa.Column(
                'user_id', sa.String(length=36), nullable=False,
            ),
            sa.Column(
                'created_at', sa.DateTime(timezone=True),
                server_default=sa.text('now()'), nullable=False,
            ),
            sa.Column(
                'updated_at', sa.DateTime(timezone=True),
                server_default=sa.text('now()'), nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ['user_id'], ['users.id'], ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id'),
        )

    # Indexes on projects (use raw SQL for IF NOT EXISTS)
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_projects_user_id '
        'ON projects (user_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_projects_user_created '
        'ON projects (user_id, created_at)'
    )

    # Add project_id to conversations
    if not _column_exists('conversations', 'project_id'):
        op.add_column(
            'conversations',
            sa.Column(
                'project_id', sa.String(length=36), nullable=True,
            ),
        )
    if not _fk_exists('conversations', 'fk_conversations_project_id'):
        op.create_foreign_key(
            'fk_conversations_project_id',
            'conversations', 'projects',
            ['project_id'], ['id'],
            ondelete='SET NULL',
        )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_conversations_project_id '
        'ON conversations (project_id)'
    )

    # Add project_id to research_tasks
    if not _column_exists('research_tasks', 'project_id'):
        op.add_column(
            'research_tasks',
            sa.Column(
                'project_id', sa.String(length=36), nullable=True,
            ),
        )
    if not _fk_exists('research_tasks', 'fk_research_tasks_project_id'):
        op.create_foreign_key(
            'fk_research_tasks_project_id',
            'research_tasks', 'projects',
            ['project_id'], ['id'],
            ondelete='SET NULL',
        )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_research_tasks_project_id '
        'ON research_tasks (project_id)'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove project_id from research_tasks
    op.drop_index(
        'ix_research_tasks_project_id', table_name='research_tasks',
    )
    op.drop_constraint(
        'fk_research_tasks_project_id', 'research_tasks',
        type_='foreignkey',
    )
    op.drop_column('research_tasks', 'project_id')

    # Remove project_id from conversations
    op.drop_index(
        'ix_conversations_project_id', table_name='conversations',
    )
    op.drop_constraint(
        'fk_conversations_project_id', 'conversations',
        type_='foreignkey',
    )
    op.drop_column('conversations', 'project_id')

    # Drop projects table
    op.drop_index('ix_projects_user_created', table_name='projects')
    op.drop_index('ix_projects_user_id', table_name='projects')
    op.drop_table('projects')
