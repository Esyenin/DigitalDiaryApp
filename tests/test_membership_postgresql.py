"""Optional integration test; never connects to an application database."""

import os
from datetime import date, time, timedelta

import pytest
from sqlalchemy import create_engine, delete, inspect, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.models import Group, Lesson, Schedule, ScheduleGroupLink, Student
from app.ui.data import repository as repository_module
from config import settings


POSTGRES_ENV = "DIGITAL_DIARY_MEMBERSHIP_POSTGRES_URL"


@pytest.mark.skipif(not os.environ.get(POSTGRES_ENV), reason="No disposable PostgreSQL test database configured")
def test_postgresql_membership_and_roster_guards(monkeypatch):
    url = make_url(os.environ[POSTGRES_ENV])
    app_url = make_url(settings.get_db_url())
    if url.get_backend_name() != "postgresql" or not url.database.startswith("test_"):
        pytest.fail(f"{POSTGRES_ENV} must name a dedicated test_ PostgreSQL database")
    if app_url.get_backend_name() == "postgresql" and app_url.database == url.database:
        pytest.fail("PostgreSQL test database must differ from the application database")

    engine = create_engine(url)
    try:
        if inspect(engine).get_table_names():
            pytest.fail("PostgreSQL membership test requires an empty database")
        monkeypatch.setattr(repository_module, "DATABASE_URL", url.render_as_string(hide_password=False))
        repo = repository_module.DiaryRepository()
        try:
            first = repo.create_group("PG-FIRST", None)
            second = repo.create_group("PG-SECOND", None)
            student = repo.create_student(first, "Ivan", "Ivanov")
            schedule = Schedule(
                day=date.today().strftime("%A"), time=time(10), odd_or_even="even",
                type="Seminar", is_assessment=True, effective_from=date.today(),
            )
            repo.session.add(schedule)
            repo.session.flush()
            repo.session.add(ScheduleGroupLink(schedule_id=schedule.id, group_id=first.id))
            repo.session.flush()
            lesson = Lesson(schedule_id=schedule.id, date=date.today())
            repo.session.add(lesson)
            repo.session.commit()
            assert [item.id for item in repo.students_for_lesson(lesson)] == [student.id]
            repo.complete_lesson_roster(lesson)
            repo.transfer_student(student, second, date.today())
            assert repo.students_for_lesson(lesson)[0].id == student.id
            with pytest.raises(DBAPIError):
                repo.session.execute(update(Student).where(Student.id == student.id).values(group_id=first.id))
            repo.session.rollback()
            assert repo.session.scalar(select(Student.group_id).where(Student.id == student.id)) == second.id
            future = Lesson(schedule_id=schedule.id, date=date.today() + timedelta(days=7))
            repo.session.add(future)
            repo.session.commit()
            moved = date.today() + timedelta(days=14)
            repo.session.execute(update(Lesson).where(Lesson.id == future.id).values(date=moved))
            repo.session.commit()
            assert repo.session.scalar(select(Lesson.date).where(Lesson.id == future.id)) == moved
            with pytest.raises(DBAPIError, match="lesson history"):
                repo.session.execute(update(Lesson).where(Lesson.id == lesson.id).values(date=moved))
            repo.session.rollback()
            assert repo.session.scalar(select(Lesson.date).where(Lesson.id == lesson.id)) == date.today()
            with pytest.raises(DBAPIError, match="lesson history"):
                repo.session.execute(delete(Lesson).where(Lesson.id == lesson.id))
            repo.session.rollback()
            future_id = future.id
            repo.session.execute(delete(Lesson).where(Lesson.id == future_id))
            repo.session.commit()
            assert repo.session.scalar(select(Lesson.id).where(Lesson.id == future_id)) is None
        finally:
            repo.close()
            repo.engine.dispose()
    finally:
        engine.dispose()
