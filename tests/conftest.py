"""Shared database fixtures. Destructive setup must never use the app database."""

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
import pytest

from app.models import Base
from config import settings


TEST_DATABASE_ENV = "DIGITAL_DIARY_TEST_DATABASE_URL"


def validated_test_database_url():
    raw_url = os.environ.get(TEST_DATABASE_ENV, "").strip()
    if not raw_url:
        raise RuntimeError(f"Set {TEST_DATABASE_ENV} to a fresh, dedicated test database.")

    url = make_url(raw_url)
    application_url = make_url(settings.get_db_url())
    if url.get_backend_name() == "sqlite":
        database = url.database
        if not database or database == ":memory:":
            raise RuntimeError("Tests require a named SQLite database file.")
        test_path = Path(database).resolve()
        if not test_path.name.startswith("test_"):
            raise RuntimeError("SQLite test database filename must start with test_.")
        if application_url.get_backend_name() == "sqlite":
            if test_path == Path(application_url.database).resolve():
                raise RuntimeError("Test database is the application database.")
    elif url.get_backend_name() == "postgresql":
        if not url.database or not url.database.startswith("test_"):
            raise RuntimeError("PostgreSQL test database name must start with test_.")
        if application_url.get_backend_name() == "postgresql" and url.database == application_url.database:
            raise RuntimeError("Test database is the application database.")
    else:
        raise RuntimeError("Only SQLite and PostgreSQL test databases are supported.")
    return url


def create_test_engine():
    url = validated_test_database_url()
    engine = create_engine(url)
    try:
        existing = set(inspect(engine).get_table_names())
        if existing:
            raise RuntimeError(
                "Test database already contains tables; use a fresh database: "
                + ", ".join(sorted(existing))
            )
        Base.metadata.create_all(bind=engine)
    except BaseException:
        engine.dispose()
        raise
    return engine


@pytest.fixture(scope="session")
def engine():
    """Create tables only in an explicitly selected, empty test database."""
    engine = create_test_engine()
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Создает изолированную сессию для каждого отдельного теста.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
