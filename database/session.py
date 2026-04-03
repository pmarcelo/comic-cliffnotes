from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

if not config.DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set in the .env file!")

engine = create_engine(config.DATABASE_URL)
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