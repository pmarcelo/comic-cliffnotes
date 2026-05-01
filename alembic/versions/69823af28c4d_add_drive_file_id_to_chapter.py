"""add drive_file_id to chapter

Revision ID: 69823af28c4d
Revises: f72bc5c00777
Create Date: 2026-04-30 19:26:31.886410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69823af28c4d'
down_revision: Union[str, Sequence[str], None] = 'f72bc5c00777'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Adds the drive_file_id column to the Chapter table
    op.add_column('chapters', sa.Column('drive_file_id', sa.String(length=255), nullable=True))

def downgrade():
    # Removes the drive_file_id column if you need to rollback
    op.drop_column('chapters', 'drive_file_id')
