# Remove OCRResult Model

Steps to remove the OCRResult table and model after migrating OCR text storage to Google Drive.

---

## Step 1: Remove Model from database/models.py

Find the `OCRResult` class definition in `database/models.py` and delete the entire class:

```python
class OCRResult(Base):
    __tablename__ = "ocrresult"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapter.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

Also remove the import: `from database.models import OCRResult` from any files that reference it (only `core/pipeline/ocr_manager.py` after the recent update).

---

## Step 2: Generate Alembic Migration to Drop Table

Run this command in the project root:

```bash
alembic revision --autogenerate -m "drop ocrresult table"
```

This creates a new migration file in `alembic/versions/` (e.g., `xxxxx_drop_ocrresult_table.py`).

---

## Step 3: Replace Migration File Contents

Open the generated migration file and replace its `upgrade()` and `downgrade()` functions:

```python
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.drop_table('ocrresult')

def downgrade() -> None:
    op.create_table(
        'ocrresult',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('chapter_id', sa.String(36), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapter.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
```

---

## Step 4: Apply the Migration

Run this command to drop the table:

```bash
alembic upgrade head
```

Monitor output:
```
INFO  [alembic.runtime.migration] Running upgrade ... drop ocrresult table
INFO  [alembic.runtime.migration] Done.
```

---

## Step 5: Rollback (if needed)

If something goes wrong:

```bash
alembic downgrade -1
```

---

## Verification

Verify the table is removed:

```bash
psql $DATABASE_URL -c "\dt ocrresult;"
```

Expected output: `Did not find any relation named "ocrresult".`

---

## Safety Notes

- ⚠️ Perform this **AFTER** all chapters have `drive_file_id` populated and verified in Google Drive
- Keep raw OCRResult table in DB for 1-2 weeks as fallback before dropping
- If you need to keep historical OCR data, export before dropping:
  ```bash
  pg_dump $DATABASE_URL --table ocrresult > ocrresult_backup.sql
  ```
