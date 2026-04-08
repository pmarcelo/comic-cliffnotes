"""backfill is_extracted from ocr_extracted

Revision ID: 30c058997ebe
Revises: c904be0ca0c5
Create Date: 2026-04-07 20:41:56.463082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30c058997ebe'
down_revision: Union[str, Sequence[str], None] = 'c904be0ca0c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 🎯 Data Backfill: If it's already OCR'd, it must have been extracted.
    op.execute(
        "UPDATE chapter_processing SET is_extracted = True WHERE ocr_extracted = True"
    )


def downgrade() -> None:
    # 🔄 Reverting: We set them back to False (standard for a downgrade)
    op.execute(
        "UPDATE chapter_processing SET is_extracted = False WHERE ocr_extracted = True"
    )
