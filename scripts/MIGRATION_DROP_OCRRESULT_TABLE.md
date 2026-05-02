# Drop OCRResult Table Migration

Complete Alembic migration instructions to remove the `ocrresult` table after migrating all OCR text to Google Drive.

---

## Step 1: Generate the Alembic Migration

Run this command in the project root:

```bash
alembic revision --autogenerate -m "drop ocrresult table"
```

This creates a new migration file in `alembic/versions/` (e.g., `xxxxx_drop_ocrresult_table.py`).

---

## Step 2: Verify and Replace Migration File Contents

Open the generated migration file (`alembic/versions/xxxxx_drop_ocrresult_table.py`) and ensure the `upgrade()` and `downgrade()` functions match exactly:

### upgrade() function:

```python
def upgrade() -> None:
    op.drop_table('ocrresult')
```

### downgrade() function:

```python
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

## Step 3: Apply the Migration

Run this command to drop the table from your local database:

```bash
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade ... drop ocrresult table
INFO  [alembic.runtime.migration] Done.
```

---

## Step 4: Delete OCRResult Model from Source Code

Edit `database/models.py` and remove the entire `OCRResult` class definition:

```python
class OCRResult(Base):
    __tablename__ = "ocrresult"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapter.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

**Remove this entire class.** Do not keep any imports of it.

---

## Step 5: Verify Table is Dropped

Query the database to confirm:

```bash
psql $DATABASE_URL -c "\dt ocrresult;"
```

Expected output:
```
Did not find any relation named "ocrresult".
```

---

## Step 6: Rollback (if needed)

If something goes wrong and you need to restore the table:

```bash
alembic downgrade -1
```

---

## Safety Checklist

- ✅ All chapters have `drive_file_id` populated and verified
- ✅ All OCR text successfully migrated to Google Drive
- ✅ `OCRManager` updated to upload directly to Drive
- ✅ `SummaryManager` updated to fetch from Drive
- ✅ Test summary generation pipeline with new Drive-based flow
- ✅ Run this migration on local database first
- ✅ Test on staging before production

---

## Backup (Optional but Recommended)

Before dropping, optionally export the table for historical records:

```bash
pg_dump $DATABASE_URL --table ocrresult --data-only > ocrresult_backup.sql
```

Store this backup for 30 days in case of rollback needs.

---

## Timeline

- **Immediate:** Run Steps 1-3 on local dev database to verify
- **After verification:** Run Steps 1-5 on staging database
- **After staging tests pass:** Run on production
- **After production confirms stable:** Clean up backup files (Step 6)
