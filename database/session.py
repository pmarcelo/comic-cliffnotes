import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

# --- SSL BOOTSTRAP ---
cert_path = os.path.expanduser("~/.postgresql/root.crt")

if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    if "COCKROACH_CA_CERT" in st.secrets:
        with open(cert_path, "w") as f:
            f.write(st.secrets["COCKROACH_CA_CERT"])
        os.environ["PGSSLROOTCERT"] = cert_path
        st.sidebar.success("🔒 SSL Certificate Injected")

# --- Database Engines ---
local_engine = None
if os.getenv("CLIFFNOTES_MODE") != "ONLINE" and config.DATABASE_URL:
    local_engine = create_engine(config.DATABASE_URL)

cloud_engine = None
if config.CLOUD_DATABASE_URL:
    # 🎯 FORCE STANDARD POSTGRES DRIVER
    # This prevents the buggy cockroachdb dialect from loading
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
        # Immediate test
        with cloud_engine.connect() as conn:
            st.sidebar.info("📖 Library: Online & Connected")
    except Exception as e:
        st.sidebar.error(f"📡 Connection Error: {str(e)}")