import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config

# -------------------------------------------------------------------------
# 🎯 1. SSL BOOTSTRAP (Crucial for Streamlit Cloud)
# -------------------------------------------------------------------------
# CockroachDB verify-full looks for a file at ~/.postgresql/root.crt
cert_path = os.path.expanduser("~/.postgresql/root.crt")

if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
    # Ensure the directory exists
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    
    # Inject the certificate from secrets into the file system
    if "COCKROACH_CA_CERT" in st.secrets:
        with open(cert_path, "w") as f:
            f.write(st.secrets["COCKROACH_CA_CERT"])
        
        # 💡 THE FORCE FIX: Explicitly tell the Postgres driver where to look
        os.environ["PGSSLROOTCERT"] = cert_path
        
        # Optional: Debug check (You can remove this once it works)
        if os.path.exists(cert_path):
            st.sidebar.success("🔒 SSL Cert Verified on Disk")
    else:
        st.error("SSL Error: COCKROACH_CA_CERT not found in Secrets.")

# -------------------------------------------------------------------------
# 2. Local Database Engine (The Command Center)
# -------------------------------------------------------------------------
local_engine = None
SessionLocal = None

# We use a try-except here so the app doesn't crash on Cloud due to local missing vars
try:
    if config.DATABASE_URL:
        local_engine = create_engine(config.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)
    elif os.getenv("CLIFFNOTES_MODE") != "ONLINE":
        st.warning("Running locally without DATABASE_URL. Check your .env file.")
except Exception as e:
    if os.getenv("CLIFFNOTES_MODE") != "ONLINE":
        st.error(f"Local Engine Error: {e}")

# -------------------------------------------------------------------------
# 3. Cloud Database Engine (The Remote Replica)
# -------------------------------------------------------------------------
cloud_engine = None

if config.CLOUD_DATABASE_URL:
    try:
        cloud_engine = create_engine(
            config.CLOUD_DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
    except Exception as e:
        st.error(f"Cloud Engine Error: {e}")