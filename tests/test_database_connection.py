from app.database.connection import normalize_database_url


def test_normalize_database_url_from_postgresql_scheme():
    assert normalize_database_url("postgresql://user:pass@host/db") == "postgresql+asyncpg://user:pass@host/db"


def test_normalize_database_url_from_postgres_scheme():
    assert normalize_database_url("postgres://user:pass@host/db") == "postgresql+asyncpg://user:pass@host/db"


def test_normalize_database_url_keeps_asyncpg_scheme():
    original = "postgresql+asyncpg://user:pass@host/db"
    assert normalize_database_url(original) == original
