import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import your Base and models so Alembic can read the schema
from database.models import Base 

# 1. FORCE LOAD THE .ENV FILE
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = os.getenv("DATABASE_URL")
    
    # INTERCEPT AND REWRITE FOR COCKROACHDB
    if url and url.startswith("postgres") and "cockroach" in url:
        url = url.replace("postgresql://", "cockroachdb://", 1)
        url = url.replace("postgres://", "cockroachdb://", 1)
        
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    # 1. PULL DIRECTLY FROM OS ENVIRONMENT
    url = os.getenv("DATABASE_URL")
    
    if not url:
        raise ValueError("DATABASE_URL is not set in the .env file!")
        
    # 2. INTERCEPT AND REWRITE FOR COCKROACHDB
    if url.startswith("postgres") and "cockroach" in url:
        url = url.replace("postgresql://", "cockroachdb://", 1)
        url = url.replace("postgres://", "cockroachdb://", 1)

    # 3. EXPLICITLY OVERRIDE THE CONFIG DICTIONARY
    ini_section = config.get_section(config.config_ini_section, {})
    ini_section["sqlalchemy.url"] = url

    connectable = engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()