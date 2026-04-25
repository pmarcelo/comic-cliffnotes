import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql.base import PGDialect

# Monkeypatch for CockroachDB version detection bypass
# CockroachDB v25.4.8 version string fails PostgreSQL regex; return hardcoded tuple
_original_get_server_version_info = PGDialect._get_server_version_info
def _patched_get_server_version_info(self, connection):
    try:
        return _original_get_server_version_info(self, connection)
    except (AssertionError, ValueError):
        # Regex failed on non-standard version string (e.g., CockroachDB)
        return (13, 0, 0)
PGDialect._get_server_version_info = _patched_get_server_version_info

# 🎯 STEP 1: Define EVERYTHING at the top level so other files can import them
SessionLocal = sessionmaker(autocommit=False, autoflush=False)
local_engine = None
cloud_engine = None
engine = None  # Global shorthand for the active engine

def initialize_database():
    """Logic to setup engines and bind the session factory."""
    global local_engine, cloud_engine, engine
    
    # We import config INSIDE the function to prevent circular import loops
    from core import config
    
    # --- 1. SSL Setup ---
    cert_path = os.path.expanduser("~/.postgresql/root.crt")
    if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        if "COCKROACH_CA_CERT" in st.secrets:
            with open(cert_path, "w") as f:
                f.write(st.secrets["COCKROACH_CA_CERT"])
            os.environ["PGSSLROOTCERT"] = cert_path

    # --- 2. Setup Local Engine ---
    if os.getenv("CLIFFNOTES_MODE") != "ONLINE" and config.DATABASE_URL:
        try:
            local_engine = create_engine(config.DATABASE_URL)
        except Exception as e:
            st.error(f"Local DB Error: {e}")

    # --- 3. Setup Cloud Engine (With Dialect Bypass) ---
    if config.CLOUD_DATABASE_URL:
        # We replace the prefix to avoid the buggy cockroachdb version check
        raw_url = config.CLOUD_DATABASE_URL
        final_url = raw_url.replace("cockroachdb://", "postgresql+psycopg2://")
        final_url = final_url.replace("postgresql://", "postgresql+psycopg2://")
        
        try:
            cloud_engine = create_engine(
                final_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={"client_encoding": "utf8"}
            )
        except Exception as e:
            st.sidebar.error(f"Cloud DB Connection Error: {e}")

    # --- 4. Final Binding ---
    engine = cloud_engine if os.getenv("CLIFFNOTES_MODE") == "ONLINE" else local_engine
    if engine:
        SessionLocal.configure(bind=engine)

# Run the initialization
initialize_database()