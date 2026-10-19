"""The test bootstrap must refuse ambiguous or populated database targets."""

import sqlite3

import pytest
from sqlalchemy import inspect

from tests import conftest as database_fixtures


def test_database_url_must_be_explicit(monkeypatch):
    monkeypatch.delenv(database_fixtures.TEST_DATABASE_ENV, raising=False)
    with pytest.raises(RuntimeError, match="Set DIGITAL_DIARY_TEST_DATABASE_URL"):
        database_fixtures.create_test_engine()


def test_application_sqlite_database_is_rejected(monkeypatch, tmp_path):
    application_db = tmp_path / "test_application.db"
    url = f"sqlite:///{application_db.as_posix()}"
    monkeypatch.setenv(database_fixtures.TEST_DATABASE_ENV, url)
    monkeypatch.setattr(type(database_fixtures.settings), "get_db_url", lambda self: url)
    with pytest.raises(RuntimeError, match="application database"):
        database_fixtures.create_test_engine()
    assert not application_db.exists()


def test_non_test_sqlite_filename_is_rejected(monkeypatch, tmp_path):
    target = tmp_path / "diary.db"
    monkeypatch.setenv(database_fixtures.TEST_DATABASE_ENV, f"sqlite:///{target.as_posix()}")
    with pytest.raises(RuntimeError, match="test_"):
        database_fixtures.create_test_engine()
    assert not target.exists()


def test_populated_database_is_not_modified(monkeypatch, tmp_path):
    target = tmp_path / "test_existing.db"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE unrelated_data (value TEXT)")
        connection.execute("INSERT INTO unrelated_data VALUES ('preserved')")
    monkeypatch.setenv(database_fixtures.TEST_DATABASE_ENV, f"sqlite:///{target.as_posix()}")
    with pytest.raises(RuntimeError, match="already contains tables"):
        database_fixtures.create_test_engine()
    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT value FROM unrelated_data").fetchone() == ("preserved",)


def test_fresh_sqlite_database_can_be_initialized(monkeypatch, tmp_path):
    target = tmp_path / "test_fresh.db"
    monkeypatch.setenv(database_fixtures.TEST_DATABASE_ENV, f"sqlite:///{target.as_posix()}")
    engine = database_fixtures.create_test_engine()
    try:
        assert set(database_fixtures.Base.metadata.tables) <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_postgresql_database_name_must_be_dedicated(monkeypatch):
    monkeypatch.setenv(
        database_fixtures.TEST_DATABASE_ENV,
        "postgresql+psycopg2://tester:secret@localhost/diary",
    )
    with pytest.raises(RuntimeError, match="test_"):
        database_fixtures.validated_test_database_url()


def test_postgresql_application_database_is_rejected_even_with_different_url(monkeypatch):
    monkeypatch.setenv(
        database_fixtures.TEST_DATABASE_ENV,
        "postgresql+psycopg2://tester:secret@localhost/test_diary",
    )
    monkeypatch.setattr(
        type(database_fixtures.settings),
        "get_db_url",
        lambda self: "postgresql+psycopg2://owner:other@database-server/test_diary",
    )
    with pytest.raises(RuntimeError, match="application database"):
        database_fixtures.validated_test_database_url()
