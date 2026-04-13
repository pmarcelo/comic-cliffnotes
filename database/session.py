import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 🎯 STEP 1: Define SessionLocal immediately to prevent ImportErrors
SessionLocal = sessionmaker(autocommit=False, autoflush=False)

def get_engine():
    from core import config
    
    # 🎯 STEP 2: Force-Inject SSL Cert
    cert_path = os.path.expanduser("~/.postgresql/root.crt")
    if os.getenv("CLIFFNOTES_MODE") == "ONLINE":
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        if "COCKROACH_CA_CERT" in st.secrets:
            with open(cert_path, "w") as f:
                f.write(st.secrets["COCKROACH_CA_CERT"])
            os.environ["PGSSLROOTCERT"] = cert_path

    # 🎯 STEP 3: Identify the URL
    raw_url = config.CLOUD_DATABASE_URL if os.getenv("CLIFFNOTES_MODE") == "ONLINE" else config.DATABASE_URL
    
    if not raw_url:
        return None

    # 🎯 STEP 4: The "Lie" to SQLAlchemy
    # We replace 'cockroachdb://' with 'postgresql+psycopg2://'
    # This prevents SQLAlchemy from even trying to use the cockroachdb dialect.
    final_url = raw_url.replace("cockroachdb://", "postgresql+psycopg2://")
    if not final_url.startswith("postgresql"):
        final_url = "postgresql+psycopg2://" + final_url.split("://")[-1]

    try:
        engine = create_engine(
            final_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            # This tells the driver to skip the version check and just work
            connect_args={"client_encoding": "utf8"}
        )
        # Debug info for the sidebar
        st.sidebar.info(f"📡 Dialect: {engine.dialect.name}")
        return engine
    except Exception as e:
        st.sidebar.error(f"❌ Connection Error: {e}")
        return None

# 🎯 STEP 5: Initialize and Bind
active_engine = get_engine()
if active_engine:
    SessionLocal.configure(bind=active_engine)
    engine = active_engine