"""Real journal integration, only on two explicitly allocated empty PostgreSQL DBs."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.models import (AssessmentEvent, Attendance, Lesson, Schedule, ScheduleGroupLink, SeatAssignment)
from app.services.attendance_proof import ProofService
from app.services.journal_activity import ActivityService
from app.ui.data import repository as repository_module
from tests.test_attendance_proof import PNG
from config import settings


def safe_url(name):
    raw = os.environ.get(name)
    if not raw:
        pytest.skip('Two dedicated empty PostgreSQL journal databases are not configured')
    url = make_url(raw)
    application = make_url(settings.get_db_url())
    if url.get_backend_name() != 'postgresql' or not (url.database or '').startswith('test_'):
        pytest.fail('Journal tests require a dedicated test_ PostgreSQL database')
    if application.get_backend_name() == 'postgresql' and application.database == url.database:
        pytest.fail('Journal test database must not be the application database')
    return url


def test_postgresql_full_journal_guards_archive_and_concurrent_seats(tmp_path,monkeypatch):
    source_url = safe_url('DIGITAL_DIARY_JOURNAL_POSTGRES_URL')
    target_url = safe_url('DIGITAL_DIARY_JOURNAL_RESTORE_POSTGRES_URL')
    assert source_url.database != target_url.database
    for url in (source_url,target_url):
        engine = create_engine(url)
        try:
            if inspect(engine).get_table_names():
                pytest.fail('Journal integration requires empty databases; nothing was removed')
        finally:
            engine.dispose()
    monkeypatch.setattr(repository_module,'DATABASE_URL',source_url.render_as_string(hide_password=False))
    repo = repository_module.DiaryRepository()
    target = None
    try:
        monday = date.today()-timedelta(days=date.today().weekday())
        year=repo.academic_action('create_year','Year',monday,monday+timedelta(weeks=52))
        term=repo.academic_action('create_term',year.id,'Term',monday,17)
        discipline=repo.academic_action('create_discipline','Discipline')
        group=repo.create_group('PG Journal',None)
        students=[repo.create_student(group,name,'Student') for name in ('Anna','Boris','Vera')]
        course=repo.academic_action('create_offering',term.id,discipline.id,'Course',[group.id])
        module=repo.academic_action('create_module',course.id,'Module',1,monday,monday+timedelta(weeks=17))
        values=dict(module_id=module.id,title='Seminar',category='seminar_start',max_points=100,required=True,attempt_policy='best')
        with pytest.raises(DBAPIError,match='lesson'):
            repo.session.add(AssessmentEvent(**values))
            repo.session.flush()
        repo.session.rollback()
        schedule=Schedule(offering_id=course.id,day='Monday',time=time(10),type='Seminar',odd_or_even='even')
        repo.session.add(schedule)
        repo.session.flush()
        repo.session.add(ScheduleGroupLink(schedule_id=schedule.id,group_id=group.id))
        repo.session.flush()
        lesson=Lesson(schedule_id=schedule.id,date=date.today())
        future=Lesson(schedule_id=schedule.id,date=date.today()+timedelta(days=1))
        repo.session.add_all([lesson,future])
        repo.session.commit()
        with pytest.raises(DBAPIError,match='future'):
            repo.session.add(Attendance(lesson_id=future.id,student_id=students[0].id,is_visited=True))
            repo.session.flush()
        repo.session.rollback()
        repo.complete_lesson_roster(lesson)
        event=repo.teaching_action('create_event',**values,lesson_id=lesson.id)
        repo.teaching_action('record_attempt',event_id=event.id,student_id=students[0].id,points=90,
            passed=True,work_completed=True,defended=False,operation_key=uuid4().hex)
        revision=repo.teaching_action('record_attendance',lesson_id=lesson.id,student_id=students[0].id,
            status='excused',reason='Documented absence',operation_key=uuid4().hex)
        proof=repo.proof_action('attach',revision_id=revision.id,filename='proof.png',content=PNG)
        assert ProofService(repo.session).read(proof.id)[2] == PNG
        room=repo.activity_action('create_room',name='Room')
        layout=repo.activity_action('create_layout',room_id=room.id,name='Version',
            seats=[dict(label='A',x=10,y=20),dict(label='B',x=200,y=20)])
        repo.activity_action('attach_layout',lesson_id=lesson.id,layout_id=layout.id)
        seats=ActivityService(repo.session).seating(lesson.id)['seats']
        first_seat,second_seat=seats[0].id,seats[1].id
        lesson_id=lesson.id
        students_ids=[student.id for student in students]
        repo.activity_action('assign_seat',lesson_id=lesson_id,student_id=students_ids[0],seat_id=first_seat,
                             reason='Assigned',operation_key=uuid4().hex)
        repo.activity_action('record_typical_behavior',lesson_id=lesson_id,student_id=students_ids[0],
                             name='Active participation',operation_key=uuid4().hex)
        assert repo.teaching_summary(course.id,students_ids[0])['earned'] == 90
        repo.session.rollback()
        def reserve(student_id):
            other=repository_module.DiaryRepository()
            try:
                other.activity_action('assign_seat',lesson_id=lesson_id,student_id=student_id,seat_id=second_seat,
                                      reason='Concurrent assignment',operation_key=uuid4().hex)
                return True
            except repository_module.RepositoryError:
                return False
            finally:
                other.close()
                other.engine.dispose()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(reserve,students_ids[1:]))
        assert sorted(results) == [False,True]
        repo.refresh()
        assert len(ActivityService(repo.session).seating(lesson_id)['assignments']) == 2
        archive=repo.export_to_xlsx(tmp_path/'journal.xlsx')
        snapshot=repo.preview_import_from_xlsx(archive,strategy='standard')
        monkeypatch.setattr(repository_module,'DATABASE_URL',target_url.render_as_string(hide_password=False))
        target=repository_module.DiaryRepository()
        target.import_from_preview(snapshot)
        assert target.teaching_summary(course.id,students_ids[0])['earned'] == 90
        assert ProofService(target.session).read(proof.id)[2] == PNG
        assert list(target.session.scalars(select(SeatAssignment.id))) == list(repo.session.scalars(select(SeatAssignment.id)))
    finally:
        repo.close()
        repo.engine.dispose()
        if target is not None:
            target.close()
            target.engine.dispose()
