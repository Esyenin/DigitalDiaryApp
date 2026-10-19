"""Migration must preserve every existing result without fabricating a full roster."""

import sqlite3
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from app.models import Base
from app.ui.data import membership_migration, repository as repository_module


def _legacy_database(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO groups (id, name) VALUES (7, 'IU7-11')"))
        connection.execute(text(
            "INSERT INTO students (id, group_id, surname, first_name) "
            "VALUES (20, 7, 'Ivanov', 'Ivan')"
        ))
        connection.execute(text(
            "INSERT INTO students (id, group_id, surname, first_name) "
            "VALUES (21, 7, 'Petrova', 'Anna')"
        ))
        connection.execute(text(
            "INSERT INTO schedules (id, series_key, revision, effective_from, "
            "odd_or_even, type, is_assessment, day, time) VALUES "
            "(42, 'legacy-series', 1, '1900-01-01', 'even', 'Seminar', 1, 'Monday', '10:00:00')"
        ))
        connection.execute(text(
            "INSERT INTO schedulegrouplinks (id, group_id, schedule_id) VALUES (61, 7, 42)"
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
            "INSERT INTO marks (id, student_id, lesson_id, data) VALUES (101, 20, 99, 87)"
        ))
        connection.execute(text(
            "INSERT INTO comments (id, student_id, lesson_id, data) "
            "VALUES (102, 20, 99, 'Passed')"
        ))
    engine.dispose()
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE groupmemberships")
        connection.execute("DROP TABLE lessonparticipants")
        for table, columns in (
            ("students", ("status", "archived_at", "archive_reason")),
            ("groups", ("is_archived", "archive_reason")),
            ("lessons", ("participants_complete", "roster_origin")),
        ):
            for column in columns:
                connection.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    return create_engine(f"sqlite:///{path}")


def test_membership_migration_preserves_ids_and_marks_uncertainty(tmp_path):
    path = tmp_path / "legacy.db"
    engine = _legacy_database(path)
    try:
        membership_migration.ensure_membership_schema(engine, as_of=date(2026, 10, 19))
        with engine.connect() as connection:
            memberships = connection.execute(text(
                "SELECT student_id, group_id, start_date, end_date, origin, known_from "
                "FROM groupmemberships ORDER BY student_id"
            )).all()
            assert tuple(memberships[0]) == (20, 7, "1900-01-01", None,
                                               "migrated_unknown", "2026-10-19")
            assert memberships[1].student_id == 21
            assert connection.execute(text(
                "SELECT lesson_id, student_id, source FROM lessonparticipants"
            )).one() == (99, 20, "evidence")
            assert connection.execute(text(
                "SELECT participants_complete, roster_origin FROM lessons WHERE id=99"
            )).one() == (0, "legacy_unknown")
            for table, row_id, value in (
                ("students", 20, "Ivanov"), ("groups", 7, "IU7-11"),
                ("lessons", 99, "History"), ("marks", 101, 87),
                ("comments", 102, "Passed"), ("attendances", 100, 1),
            ):
                column = {
                    "students": "surname", "groups": "name", "lessons": "topic",
                    "marks": "data", "comments": "data", "attendances": "is_visited",
                }[table]
                assert connection.execute(text(
                    f"SELECT {column} FROM {table} WHERE id=:id"
                ), {"id": row_id}).scalar_one() == value
        assert len(list(tmp_path.glob("legacy.db.pre-membership-*.bak"))) == 1
        membership_migration.ensure_membership_schema(engine, as_of=date(2026, 10, 20))
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM groupmemberships")).scalar() == 2
            assert connection.execute(text("SELECT count(*) FROM lessonparticipants")).scalar() == 1
        assert len(list(tmp_path.glob("legacy.db.pre-membership-*.bak"))) == 1
    finally:
        engine.dispose()


def test_legacy_lesson_reports_only_proven_participants(tmp_path, monkeypatch):
    path = tmp_path / "legacy_stats.db"
    engine = _legacy_database(path)
    engine.dispose()
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{path}")
    repo = repository_module.DiaryRepository()
    try:
        lesson = repo.get_lesson(99)
        assert {student.id for student in repo.students_for_lesson(lesson)} == {20}
        assert repo.lesson_attendance_summary(lesson) == {
            "total": 1, "present": 1, "absent": "-", "rate": "-",
        }
        assert repo.group_stats(repo.get_group(7))["attendance"] == "-"
        assert repo.student_stats(repo.get_student(20))["attendance"] == "-"
        assert repo.student_stats(repo.get_student(21))["attendance"] == "-"
    finally:
        repo.close()
        repo.engine.dispose()


def test_failed_membership_migration_rolls_back(tmp_path, monkeypatch):
    engine = _legacy_database(tmp_path / "rollback.db")
    original = membership_migration._sqlite_guards

    def fail_after_backfill(connection):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(membership_migration, "_sqlite_guards", fail_after_backfill)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            membership_migration.ensure_membership_schema(engine)
        with engine.connect() as connection:
            assert "status" not in {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(students)")
            }
            assert connection.execute(text(
                "SELECT count(*) FROM sqlite_master WHERE type='table' "
                "AND name='groupmemberships'"
            )).scalar() == 0
            assert connection.execute(text("SELECT data FROM marks WHERE id=101")).scalar() == 87
        monkeypatch.setattr(membership_migration, "_sqlite_guards", original)
        membership_migration.ensure_membership_schema(engine)
    finally:
        engine.dispose()
