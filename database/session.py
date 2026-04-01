import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Grab the exact same URL you used for Alembic
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set!")

# 2. Create the Engine (The core connection to Postgres)
# Set echo=True if you ever want to see the raw SQL queries printing in your terminal
engine = create_engine(DATABASE_URL, echo=False)

# 3. Create the Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. The Dependency Generator
def get_db():
    """
    Creates a new database session for a task, and ensures it 
    safely closes when the task is done, even if it crashes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()