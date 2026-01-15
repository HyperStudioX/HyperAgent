"""add file_hash and remove redundant filename column

Revision ID: add_file_hash
Revises: 66e6ef6e1221
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_file_hash'
down_revision = '66e6ef6e1221'  # add_files_and_message_attachments_tables
branch_labels = None
depends_on = None


def upgrade():
    # Add file_hash column to files table
    op.add_column('files', sa.Column('file_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_files_file_hash'), 'files', ['file_hash'], unique=False)

    # Remove redundant filename column (original_filename is used instead)
    op.drop_column('files', 'filename')


def downgrade():
    # Restore filename column
    op.add_column('files', sa.Column('filename', sa.String(length=255), nullable=False, server_default=''))

    # Remove file_hash column and index
    op.drop_index(op.f('ix_files_file_hash'), table_name='files')
    op.drop_column('files', 'file_hash')
