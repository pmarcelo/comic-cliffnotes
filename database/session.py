import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

# -------------------------------------------------------------------------
# 1. Local Database (The Master Record)
# -------------------------------------------------------------------------
if not config.DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set in the .env file!")

local_engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

# -------------------------------------------------------------------------
# 2. Cloud Database (The Read Replica)
# -------------------------------------------------------------------------
CLOUD_DB_URL = os.getenv("CLOUD_DATABASE_URL")

cloud_engine = None
CloudSession = None

if CLOUD_DB_URL:
    # 🎯 FIXED: Updated the interceptor to catch "cockroach" in the cluster URL
    if CLOUD_DB_URL.startswith("postgres") and "cockroach" in CLOUD_DB_URL:
        CLOUD_DB_URL = CLOUD_DB_URL.replace("postgresql://", "cockroachdb://", 1)
        CLOUD_DB_URL = CLOUD_DB_URL.replace("postgres://", "cockroachdb://", 1)

    cloud_engine = create_engine(
        CLOUD_DB_URL, 
        pool_size=5, 
        max_overflow=10,
        pool_pre_ping=True
    )
    CloudSession = sessionmaker(autocommit=False, autoflush=False, bind=cloud_engine)

# -------------------------------------------------------------------------
# 3. Dependency Generators (The Routers)
# -------------------------------------------------------------------------

def get_db():
    """Yields the Master Local Database (PostgreSQL)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_cloud_db():
    """Yields the Cloud Replica Database (CockroachDB)."""
    if not CloudSession:
        raise Exception("CLOUD_DATABASE_URL is not set. Cannot connect to cloud.")
    db = CloudSession()
    try:
        yield db
    finally:
        db.close()

def get_ui_db():
    """Context-Aware Router for Streamlit UI."""
    IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"
    
    if IS_ONLINE and CloudSession:
        return get_cloud_db()
    return get_db()