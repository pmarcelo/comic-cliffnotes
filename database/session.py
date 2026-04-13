import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

# -------------------------------------------------------------------------
# 1. Local Database (The Master Record)
# -------------------------------------------------------------------------
if not config.DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set in the .env file!")

# Restored to use your existing Local PostgreSQL database
local_engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

# -------------------------------------------------------------------------
# 2. Cloud Database (The Read Replica)
# -------------------------------------------------------------------------
# Uses a distinct variable to prevent overriding your local Postgres connection
CLOUD_DB_URL = os.getenv("CLOUD_DATABASE_URL")

cloud_engine = None
CloudSession = None

if CLOUD_DB_URL:
    if CLOUD_DB_URL.startswith("postgres://"):
        CLOUD_DB_URL = CLOUD_DB_URL.replace("postgres://", "postgresql://", 1)
        
    if "cockroachdb" not in CLOUD_DB_URL and "crdb" in CLOUD_DB_URL:
        CLOUD_DB_URL = CLOUD_DB_URL.replace("postgresql://", "cockroachdb://", 1)

    cloud_engine = create_engine(CLOUD_DB_URL, pool_size=5, max_overflow=10)
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
        raise Exception("CLOUD_DATABASE_URL environment variable is not set. Cannot connect to cloud.")
    db = CloudSession()
    try:
        yield db
    finally:
        db.close()

def get_ui_db():
    """Context-Aware Router for Streamlit UI."""
    IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"
    
    # If hosted on Streamlit Cloud, st.secrets will map DATABASE_URL to CLOUD_DATABASE_URL
    # via the environment variables we set in the Streamlit Dashboard.
    if IS_ONLINE and CloudSession:
        return get_cloud_db()
    return get_db()