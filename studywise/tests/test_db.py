from sqlalchemy.engine import make_url

from app.db import normalize_database_url


def test_render_postgres_urls_use_installed_psycopg_driver():
    for url in (
        "postgres://student:secret@db.example/study",
        "postgresql://student:secret@db.example/study",
        "postgresql+psycopg://student:secret@db.example/study",
    ):
        assert make_url(normalize_database_url(url)).drivername == "postgresql+psycopg"


def test_sqlite_url_remains_unchanged():
    assert normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
