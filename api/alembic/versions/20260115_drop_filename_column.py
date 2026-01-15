"""drop redundant filename column

Revision ID: drop_filename
Revises: add_file_hash
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'drop_filename'
down_revision = 'add_file_hash'
branch_labels = None
depends_on = None


def upgrade():
    # Remove redundant filename column (original_filename is used instead)
    op.drop_column('files', 'filename')


def downgrade():
    # Restore filename column
    op.add_column('files', sa.Column('filename', sa.String(length=255), nullable=False, server_default=''))
