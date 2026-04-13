import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

# -------------------------------------------------------------------------
# 1. SSL BOOTSTRAP (For Streamlit Cloud)
# -------------------------------------------------------------------------
cert_path = os.path.expanduser("~/.postgresql/root.crt")

if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    if "COCKROACH_CA_CERT" in st.secrets:
        with open(cert_path, "w") as f:
            f.write(st.secrets["COCKROACH_CA_CERT"])
        # Explicitly tell the driver to use this file
        os.environ["PGSSLROOTCERT"] = cert_path
        st.sidebar.success("🔒 SSL Certificate Injected")

# -------------------------------------------------------------------------
# 2. ENGINE INITIALIZATION
# -------------------------------------------------------------------------
local_engine = None
cloud_engine = None

# --- Setup Local Engine ---
if os.getenv("CLIFFNOTES_MODE") != "ONLINE" and config.DATABASE_URL:
    local_engine = create_engine(config.DATABASE_URL)

# --- Setup Cloud Engine (With Dialect Bypass) ---
if config.CLOUD_DATABASE_URL:
    # Force standard postgres driver to bypass the CockroachDB version bug
    raw_url = config.CLOUD_DATABASE_URL
    final_url = raw_url.replace("cockroachdb://", "postgresql+psycopg2://")
    final_url = final_url.replace("postgresql://", "postgresql+psycopg2://")

    try:
        cloud_engine = create_engine(
            final_url, 
            pool_size=5, 
            max_overflow=10, 
            pool_pre_ping=True
        )
    except Exception as e:
        st.sidebar.error(f"📡 Cloud DB Error: {str(e)}")

# -------------------------------------------------------------------------
# 3. EXPORTS (The fix for your ImportError)
# -------------------------------------------------------------------------
# We determine which engine to use as the primary based on the environment
active_engine = cloud_engine if os.getenv("CLIFFNOTES_MODE") == "ONLINE" else local_engine

# This is the line your app is looking for:
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=active_engine
)

# Export engines for direct access if needed (like in render_index)
engine = active_engine