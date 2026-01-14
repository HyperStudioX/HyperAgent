"""add files and message attachments tables

Revision ID: 66e6ef6e1221
Revises: 35f727c26098
Create Date: 2026-01-15 00:41:21.552634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66e6ef6e1221'
down_revision: Union[str, Sequence[str], None] = '35f727c26098'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create files table
    op.create_table(
        'files',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('storage_bucket', sa.String(), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('extraction_status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key')
    )
    op.create_index(op.f('ix_files_user_id'), 'files', ['user_id'], unique=False)

    # Create message_attachments table
    op.create_table(
        'message_attachments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('message_id', sa.String(length=36), nullable=False),
        sa.Column('file_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['conversation_messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_message_attachments_file_id'), 'message_attachments', ['file_id'], unique=False)
    op.create_index(op.f('ix_message_attachments_message_id'), 'message_attachments', ['message_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_message_attachments_message_id'), table_name='message_attachments')
    op.drop_index(op.f('ix_message_attachments_file_id'), table_name='message_attachments')
    op.drop_table('message_attachments')
    op.drop_index(op.f('ix_files_user_id'), table_name='files')
    op.drop_table('files')
