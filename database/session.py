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

# 🎯 Define engine at module level so other files can import it
SessionLocal = sessionmaker(autocommit=False, autoflush=False)
engine = None

def initialize_database():
    """Initialize the database engine and bind the session factory."""
    global engine

    # We import config INSIDE the function to prevent circular import loops
    from core import config

    if not config.DATABASE_URL:
        st.error("DATABASE_URL not set in .env")
        return

    # SSL setup for cloud databases
    cert_path = os.path.expanduser("~/.postgresql/root.crt")
    if "cockroach" in config.DATABASE_URL.lower() or "postgresql" in config.DATABASE_URL.lower():
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        if "COCKROACH_CA_CERT" in st.secrets:
            with open(cert_path, "w") as f:
                f.write(st.secrets["COCKROACH_CA_CERT"])
            os.environ["PGSSLROOTCERT"] = cert_path

    # Normalize the database URL for CockroachDB
    final_url = config.DATABASE_URL
    final_url = final_url.replace("cockroachdb://", "postgresql+psycopg2://")
    final_url = final_url.replace("postgresql://", "postgresql+psycopg2://")

    try:
        engine = create_engine(
            final_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"client_encoding": "utf8"}
        )
        SessionLocal.configure(bind=engine)
    except Exception as e:
        st.error(f"Database Connection Error: {e}")

# Run the initialization
initialize_database()