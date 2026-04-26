# OCR Text Migration: Database → Google Drive

Schema preparation to store Google Drive file references instead of raw OCR text in database.

---

## Step 1: Generate the Alembic Migration

Run this command in the project root:

```bash
alembic revision --autogenerate -m "add drive_file_id to OCRResult table"
```

This creates a new migration file in `alembic/versions/` (e.g., `xxxxx_add_drive_file_id_to_ocrresult.py`).

---

## Step 2: Replace Migration File Contents

Open the generated migration file and replace its `upgrade()` and `downgrade()` functions with the code below:

```python
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column(
        'ocrresult',
        sa.Column('drive_file_id', sa.String(255), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('ocrresult', 'drive_file_id')
```

---

## Step 3: Apply the Migration

Run this command to apply the migration to the local database:

```bash
alembic upgrade head
```

Monitor the output for success confirmation:
```
INFO  [alembic.runtime.migration] Running upgrade ... add drive_file_id to ocrresult table
INFO  [alembic.runtime.migration] Done.
```

---

## Step 4: Rollback (if needed)

If something goes wrong, rollback to the previous schema:

```bash
alembic downgrade -1
```

---

## Verification

After upgrade, verify the column exists:

```bash
psql $DATABASE_URL -c "\d ocrresult;" | grep drive_file_id
```

Expected output:
```
 drive_file_id | character varying(255) |
```

---

## Notes

- `drive_file_id` is nullable to allow gradual migration of existing chapters
- Once all chapters have `drive_file_id` populated and raw text migrated to Drive, you can later make it `NOT NULL` and drop the `raw_text` column
- Keep the raw text in database temporarily during the transition phase for safety
