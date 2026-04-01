import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# UPDATE: Ensures Alembic can find the 'database' package in your project root
sys.path.append(os.getcwd())

# UPDATE: Points to your actual models
from database.models import Base
target_metadata = Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # UPDATE: Pulls URL from environment variable for security
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    
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
    # UPDATE: Prioritizes DATABASE_URL from your environment
    db_url = os.getenv("DATABASE_URL")
    
    section = config.get_section(config.config_ini_section, {})
    if db_url:
        section["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # UPDATE: Detects changes to column types (e.g., Integer to BigInteger)
            compare_type=True 
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()