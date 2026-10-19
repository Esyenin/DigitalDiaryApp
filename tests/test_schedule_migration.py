import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import Base
from app.ui.data import schedule_migration


def _legacy_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE schedules ("
            "id INTEGER PRIMARY KEY, created_at DATETIME, updated_at DATETIME, "
            "odd_or_even VARCHAR(16), type VARCHAR(64), is_assessment BOOLEAN, "
            "day VARCHAR(16), time TIME)"
        )
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO schedules VALUES "
            "(42, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'even', 'Seminar', 1, 'Monday', '10:00:00')"
        ))
        connection.execute(text(
            "INSERT INTO groups (id, name) VALUES (7, 'IU7-11')"
        ))
        connection.execute(text(
            "INSERT INTO students (id, group_id, surname, first_name) "
            "VALUES (20, 7, 'Ivanov', 'Ivan')"
        ))
        connection.execute(text(
            "INSERT INTO schedulegrouplinks (id, group_id, schedule_id) "
            "VALUES (61, 7, 42)"
        ))
        connection.execute(text(
            "INSERT INTO lessons (id, schedule_id, topic, date) "
            "VALUES (99, 42, 'History', '2026-02-09')"
        ))
        connection.execute(text(
            "INSERT INTO attendances (id, student_id, lesson_id, is_visited) "
            "VALUES (100, 20, 99, 1)"
        ))
        connection.execute(text(
            "INSERT INTO marks (id, student_id, lesson_id, data) "
            "VALUES (101, 20, 99, 87)"
        ))
        connection.execute(text(
            "INSERT INTO comments (id, student_id, lesson_id, data) "
            "VALUES (102, 20, 99, 'Passed')"
        ))
    return engine


def test_migration_preserves_every_id_and_creates_backup(tmp_path):
    path = tmp_path / "test_legacy.db"
    engine = _legacy_database(path)
    try:
        schedule_migration.ensure_schedule_schema(engine)
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT id, series_key, revision, effective_from, effective_until "
                "FROM schedules"
            )).one()
            assert row.id == 42
            assert row.series_key
            assert row.revision == 1
            assert row.effective_from == "1900-01-01"
            assert row.effective_until is None
            expected = {
                "schedulegrouplinks": (61, "group_id", 7),
                "lessons": (99, "topic", "History"),
                "attendances": (100, "is_visited", 1),
                "marks": (101, "data", 87),
                "comments": (102, "data", "Passed"),
            }
            for table, (row_id, field, value) in expected.items():
                assert connection.execute(
                    text(f"SELECT {field} FROM {table} WHERE id = :id"), {"id": row_id}
                ).scalar_one() == value
        backups = list(tmp_path.glob("test_legacy.db.pre-schedule-version-*.bak"))
        assert len(backups) == 1
        with sqlite3.connect(backups[0]) as backup:
            assert "series_key" not in {
                column[1] for column in backup.execute("PRAGMA table_info(schedules)")
            }
        schedule_migration.ensure_schedule_schema(engine)
        assert len(list(tmp_path.glob("test_legacy.db.pre-schedule-version-*.bak"))) == 1
    finally:
        engine.dispose()


def test_failed_migration_rolls_back_schema_and_data(tmp_path, monkeypatch):
    path = tmp_path / "test_rollback.db"
    engine = _legacy_database(path)
    original = schedule_migration._migrate

    def fail_after_migration(connection):
        original(connection)
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(schedule_migration, "_migrate", fail_after_migration)
    try:
        with pytest.raises(RuntimeError, match="simulated failure"):
            schedule_migration.ensure_schedule_schema(engine)
        assert "series_key" not in {
            column["name"] for column in inspect(engine).get_columns("schedules")
        }
        with engine.connect() as connection:
            assert connection.execute(text("SELECT id FROM schedules")).scalar_one() == 42
            assert connection.execute(text("SELECT data FROM marks")).scalar_one() == 87
    finally:
        engine.dispose()


def test_existing_sqlite_database_replaces_old_link_update_guard(tmp_path):
    path = tmp_path / "test_existing_guard.db"
    engine = _legacy_database(path)
    try:
        schedule_migration.ensure_schedule_schema(engine)
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO schedules (id, series_key, revision, effective_from, "
                "odd_or_even, type, is_assessment, day, time) VALUES "
                "(43, 'unused-series', 1, '1900-01-01', "
                "'even', 'Seminar', 0, 'Tuesday', '11:00:00')"
            ))
            connection.execute(text("INSERT INTO groups (id, name) VALUES (8, 'IU7-12')"))
            connection.execute(text(
                "INSERT INTO schedulegrouplinks (id, group_id, schedule_id) "
                "VALUES (62, 8, 43)"
            ))
            connection.exec_driver_sql("DROP TRIGGER schedule_link_history_update")
            connection.exec_driver_sql(
                "CREATE TRIGGER schedule_link_history_update BEFORE UPDATE "
                "ON schedulegrouplinks WHEN EXISTS "
                "(SELECT 1 FROM lessons WHERE schedule_id = OLD.schedule_id) "
                "BEGIN SELECT RAISE(ABORT, 'old guard'); END"
            )

        schedule_migration.ensure_schedule_schema(engine)
        with engine.begin() as connection:
            with pytest.raises(IntegrityError, match="historical group links are immutable"):
                connection.execute(text(
                    "UPDATE schedulegrouplinks SET schedule_id = 42 WHERE id = 62"
                ))
            assert connection.execute(text(
                "SELECT schedule_id FROM schedulegrouplinks WHERE id = 62"
            )).scalar_one() == 43
    finally:
        engine.dispose()
