"""Optional integration test for a newly created, disposable PostgreSQL database."""

import os
from datetime import date, time, timedelta

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

from app.models import Attendance, Comment, Group, Lesson, Mark, Schedule, ScheduleGroupLink, Student
from app.ui.data import repository as repository_module
from app.ui.data.calendar import SemesterSettings, monday_for
from app.ui.data.schedule_migration import ensure_schedule_schema
from config import settings


POSTGRES_ENV = "DIGITAL_DIARY_SCHEDULE_POSTGRES_URL"


@pytest.mark.skipif(not os.environ.get(POSTGRES_ENV), reason="No disposable PostgreSQL test database configured")
def test_postgresql_migration_and_version_switch(monkeypatch):
    url = make_url(os.environ[POSTGRES_ENV])
    app_url = make_url(settings.get_db_url())
    if url.get_backend_name() != "postgresql" or not url.database.startswith("test_"):
        pytest.fail(f"{POSTGRES_ENV} must name a dedicated test_ PostgreSQL database")
    if app_url.get_backend_name() == "postgresql" and app_url.database == url.database:
        pytest.fail("PostgreSQL test database must differ from the application database")

    engine = create_engine(url)
    try:
        if inspect(engine).get_table_names():
            pytest.fail("PostgreSQL migration test requires an empty database")
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE schedules (id SERIAL PRIMARY KEY, created_at TIMESTAMP, "
                "updated_at TIMESTAMP, odd_or_even VARCHAR(16), type VARCHAR(64), "
                "is_assessment BOOLEAN, day VARCHAR(16), time TIME)"
            ))
            connection.execute(text(
                "INSERT INTO schedules VALUES "
                "(42, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'even', 'Seminar', true, 'Monday', '10:00')"
            ))
        ensure_schedule_schema(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT revision FROM schedules WHERE id = 42")).scalar_one() == 1

        monkeypatch.setattr(repository_module, "DATABASE_URL", url.render_as_string(hide_password=False))
        repo = repository_module.DiaryRepository()
        try:
            schedule = repo.session.get(Schedule, 42)
            group = Group(name="PG-TEST")
            repo.session.add(group)
            repo.session.flush()
            student = Student(group_id=group.id, surname="Ivanov", first_name="Ivan")
            repo.session.add_all([student, ScheduleGroupLink(group_id=group.id, schedule_id=42)])
            repo.session.flush()
            past_date = monday_for(date.today() - timedelta(days=7))
            future_start = monday_for(date.today() + timedelta(days=14))
            lesson = Lesson(schedule_id=42, date=past_date, topic="Recorded")
            repo.session.add(lesson)
            repo.session.flush()
            repo.session.add_all([
                Attendance(student_id=student.id, lesson_id=lesson.id, is_visited=True),
                Mark(student_id=student.id, lesson_id=lesson.id, data=88),
                Comment(student_id=student.id, lesson_id=lesson.id, data="Saved"),
            ])
            repo.session.commit()
            result_ids = (lesson.id, repo.session.scalar(select(Attendance.id)),
                          repo.session.scalar(select(Mark.id)), repo.session.scalar(select(Comment.id)))
            new_schedule = repo.update_schedule(
                schedule, None, [group], "Tuesday", time(11), "even", "Lab Work",
                True, SemesterSettings(start_date=future_start, total_weeks=4),
                effective_from=future_start,
            )
            assert new_schedule.id != 42
            assert repo.session.get(Lesson, result_ids[0]).schedule_id == 42
            assert repo.session.get(Attendance, result_ids[1]).is_visited is True
            assert repo.session.get(Mark, result_ids[2]).data == 88
            assert repo.session.get(Comment, result_ids[3]).data == "Saved"
        finally:
            repo.close()
            repo.engine.dispose()
    finally:
        engine.dispose()
