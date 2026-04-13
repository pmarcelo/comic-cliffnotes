import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from database.models import Base

# 1. Load the URL (which is currently your CockroachDB link)
load_dotenv()
url = os.getenv("DATABASE_URL")

# 2. Apply the CockroachDB dialect fix
if url and url.startswith("postgres") and "cockroach" in url:
    url = url.replace("postgresql://", "cockroachdb://", 1)
    url = url.replace("postgres://", "cockroachdb://", 1)

print(f"Connecting to: {url.split('@')[1]}") # Hide password in logs

# 3. Connect and create all tables directly from models.py
engine = create_engine(url)

print("Building tables on CockroachDB...")
Base.metadata.create_all(engine)
print("✅ Cloud Database Initialized Successfully!")