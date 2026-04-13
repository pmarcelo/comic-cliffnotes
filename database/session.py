import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

# -------------------------------------------------------------------------
# 🎯 1. SSL & ENVIRONMENT BOOTSTRAP
# -------------------------------------------------------------------------
cert_path = os.path.expanduser("~/.postgresql/root.crt")

if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    if "COCKROACH_CA_CERT" in st.secrets:
        with open(cert_path, "w") as f:
            f.write(st.secrets["COCKROACH_CA_CERT"])
        os.environ["PGSSLROOTCERT"] = cert_path
        st.sidebar.success("🔒 SSL Certificate Injected")

# -------------------------------------------------------------------------
# 2. Local Database Engine
# -------------------------------------------------------------------------
local_engine = None
SessionLocal = None

if os.getenv("CLIFFNOTES_MODE") != "ONLINE":
    if config.DATABASE_URL:
        local_engine = create_engine(config.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

# -------------------------------------------------------------------------
# 3. Cloud Database Engine (The "Dialect Bypass" Version)
# -------------------------------------------------------------------------
cloud_engine = None

if config.CLOUD_DATABASE_URL:
    # 🕵️‍♂️ DEBUG: Let's see what we're actually working with (Safe version)
    # st.sidebar.write(f"Raw URL Prefix: {config.CLOUD_DATABASE_URL.split(':')[0]}")

    # 🎯 FORCE BYPASS: If the URL has 'cockroachdb', swap it to standard postgres
    # This prevents the sqlalchemy-cockroachdb library from ever running its version check.
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
        
        # Immediate Connection Test
        with cloud_engine.connect() as conn:
            st.sidebar.info("📖 Library: Online & Connected")
            
    except Exception as e:
        # If we still fail, show the error in the sidebar for easy debugging
        st.sidebar.error(f"📡 Connection Error: {str(e)}")