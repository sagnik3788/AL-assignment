from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.config import get_settings
from app.db import Base, engine, is_postgres
from app import models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = get_settings().database_url
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
target_metadata = Base.metadata
version_table_schema = "document_qa" if is_postgres else None


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, version_table_schema=version_table_schema)
    if is_postgres:
        context.execute("CREATE SCHEMA IF NOT EXISTS document_qa")
        context.execute("SET search_path TO document_qa, public")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    with engine.begin() as connection:
        if is_postgres:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS document_qa"))
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, version_table_schema=version_table_schema)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
