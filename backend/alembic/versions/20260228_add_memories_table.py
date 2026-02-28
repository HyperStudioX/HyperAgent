"""Add memories table

Revision ID: add_memories
Revises: add_projects
Create Date: 2026-02-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision: str = 'add_memories'
down_revision: Union[str, Sequence[str], None] = 'add_projects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists (handles dev auto-create)."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists('memories'):
        op.create_table(
            'memories',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=255), nullable=False),
            sa.Column('memory_type', sa.String(length=50), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('metadata_json', sa.Text(), nullable=True, server_default='{}'),
            sa.Column('source_conversation_id', sa.String(length=255), nullable=True),
            sa.Column(
                'created_at', sa.DateTime(timezone=True),
                server_default=sa.text('now()'), nullable=False,
            ),
            sa.Column(
                'last_accessed', sa.DateTime(timezone=True),
                server_default=sa.text('now()'), nullable=False,
            ),
            sa.Column('access_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.PrimaryKeyConstraint('id'),
        )

    # Indexes
    op.execute(
        'CREATE INDEX IF NOT EXISTS idx_memories_user_id '
        'ON memories (user_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS idx_memories_type '
        'ON memories (user_id, memory_type)'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_memories_type', table_name='memories')
    op.drop_index('idx_memories_user_id', table_name='memories')
    op.drop_table('memories')
