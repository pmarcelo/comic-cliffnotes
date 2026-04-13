import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

# -------------------------------------------------------------------------
# 🎯 1. SSL BOOTSTRAP (Crucial for Streamlit Cloud)
# -------------------------------------------------------------------------
cert_path = os.path.expanduser("~/.postgresql/root.crt")

if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
    # Ensure the directory exists
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    
    # Inject the certificate from secrets into the file system
    if "COCKROACH_CA_CERT" in st.secrets:
        with open(cert_path, "w") as f:
            f.write(st.secrets["COCKROACH_CA_CERT"])
        
        # Force the Postgres driver to use this specific certificate file
        os.environ["PGSSLROOTCERT"] = cert_path
        
        # Status check for the sidebar
        if os.path.exists(cert_path):
            st.sidebar.success("🔒 SSL Certificate Injected")
    else:
        st.sidebar.error("❌ SSL Error: COCKROACH_CA_CERT not found in Secrets.")

# -------------------------------------------------------------------------
# 2. Local Database Engine (The Command Center)
# -------------------------------------------------------------------------
local_engine = None
SessionLocal = None

if os.getenv("CLIFFNOTES_MODE") != "ONLINE":
    if config.DATABASE_URL:
        local_engine = create_engine(config.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

# -------------------------------------------------------------------------
# 3. Cloud Database Engine (The Dialect Bypass Version)
# -------------------------------------------------------------------------
cloud_engine = None

if config.CLOUD_DATABASE_URL:
    # 🎯 BYPASS THE COCKROACHDB DIALECT BUG
    # We force the URL to use standard postgresql+psycopg2
    # This avoids the sqlalchemy-cockroachdb library and its broken version check.
    raw_url = config.CLOUD_DATABASE_URL
    if "cockroachdb://" in raw_url:
        final_url = raw_url.replace("cockroachdb://", "postgresql+psycopg2://")
    else:
        final_url = raw_url

    try:
        cloud_engine = create_engine(
            final_url, 
            pool_size=5, 
            max_overflow=10, 
            pool_pre_ping=True
        )
        
        # Immediate Connection Test to verify the SSL handshake
        with cloud_engine.connect() as conn:
            st.sidebar.info("📖 Library: Online & Connected")
            
    except Exception as e:
        st.sidebar.error(f"📡 Connection Error: {str(e)}")