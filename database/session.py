import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# -------------------------------------------------------------------------
# 🎯 1. DEFINITIONS FIRST (Prevents Circular Import Errors)
# -------------------------------------------------------------------------
# We create the session factory immediately. We will bind the engine later.
SessionLocal = sessionmaker(autocommit=False, autoflush=False)
local_engine = None
cloud_engine = None

# -------------------------------------------------------------------------
# 2. SSL BOOTSTRAP
# -------------------------------------------------------------------------
cert_path = os.path.expanduser("~/.postgresql/root.crt")
if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    if "COCKROACH_CA_CERT" in st.secrets:
        with open(cert_path, "w") as f:
            f.write(st.secrets["COCKROACH_CA_CERT"])
        os.environ["PGSSLROOTCERT"] = cert_path

# -------------------------------------------------------------------------
# 3. LATE IMPORTS & ENGINE BINDING
# -------------------------------------------------------------------------
# We import config HERE to ensure SessionLocal already exists if a loop occurs
from core import config

# Setup Local
if os.getenv("CLIFFNOTES_MODE") != "ONLINE" and config.DATABASE_URL:
    local_engine = create_engine(config.DATABASE_URL)

# Setup Cloud
if config.CLOUD_DATABASE_URL:
    raw_url = config.CLOUD_DATABASE_URL
    final_url = raw_url.replace("cockroachdb://", "postgresql+psycopg2://")
    final_url = final_url.replace("postgresql://", "postgresql+psycopg2://")
    try:
        cloud_engine = create_engine(final_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
    except Exception as e:
        st.sidebar.error(f"📡 Cloud DB Error: {str(e)}")

# 🎯 BIND THE SESSION TO THE ACTIVE ENGINE
active_engine = cloud_engine if os.getenv("CLIFFNOTES_MODE") == "ONLINE" else local_engine
SessionLocal.configure(bind=active_engine)