from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


url = get_settings().database_url
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
is_postgres = url.startswith("postgresql")
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
if is_postgres:
    connect_args["options"] = "-csearch_path=document_qa,public"
engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


if url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")


def create_schema():
    from app import models  # noqa: F401

    with engine.begin() as connection:
        if is_postgres:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS document_qa"))
        Base.metadata.create_all(connection)
