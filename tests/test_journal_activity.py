"""Activity history uses fresh SQLite files; no application database access."""
from datetime import date, time
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from app.models import Base, Group, Student, Schedule, Lesson, GroupMembership, ScheduleGroupLink
from app.models.journal_activity import Seat, SeatAssignment, BehaviorEvent
from app.services.journal_activity import ActivityService, ActivityError
from app.ui.data.activity_migration import ensure_activity_schema
from app.ui.data.activity_migration import install_activity_guards


@pytest.fixture
def activity():
    folder = Path('build/activity_tests')
    folder.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f'sqlite:///{folder / ("test_" + uuid4().hex + ".db")}')
    @event.listens_for(engine, 'connect')
    def fk(dbapi, _):
        dbapi.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    ensure_activity_schema(engine)
    with Session(engine, expire_on_commit=False) as session:
        group = Group(name='Group')
        session.add(group)
        session.flush()
        session.add_all([Student(id=i, group_id=group.id, surname='Student', first_name=str(i)) for i in (1, 2)])
        schedule = Schedule(day='Monday', time=time(10), type='Seminar', odd_or_even='all')
        session.add(schedule)
        session.flush()
        session.add(ScheduleGroupLink(schedule_id=schedule.id, group_id=group.id))
        session.add_all([GroupMembership(student_id=i, group_id=group.id, start_date=date(2030, 1, 1), known_from=date(2030, 1, 1), origin='recorded') for i in (1, 2)])
        lesson = Lesson(schedule_id=schedule.id, date=date(2030, 1, 7))
        session.add(lesson)
        session.commit()
        service = ActivityService(session)
        room = service.create_room('Room')
        layout = service.create_layout(room.id, 'Version', [dict(label='A', x=10, y=20), dict(label='B', x=180, y=20)])
        service.attach_layout(lesson.id, layout.id)
        session.commit()
        yield service, lesson.id
    engine.dispose()


def test_seating_revision_and_retry(activity):
    service, lesson = activity
    seats = service.seating(lesson)['seats']
    first = service.assign_seat(lesson, 1, seats[0].id, 'Initial', 'one')
    assert service.assign_seat(lesson, 1, seats[0].id, 'Initial', 'one').id == first.id
    second = service.assign_seat(lesson, 1, seats[1].id, 'Correction', 'two')
    assert second.previous_id == first.id
    service.unassign_seat(lesson, 1, 'Leave', 'three')
    assert not service.seating(lesson)['assignments']
    assert len(service.seating(lesson)['history']) == 3


def test_duplicate_and_rollback(activity):
    service, lesson = activity
    seat = service.seating(lesson)['seats'][0]
    service.assign_seat(lesson, 1, seat.id, 'Initial', 'one')
    service.session.commit()
    with pytest.raises(DBAPIError):
        service.assign_seat(lesson, 2, seat.id, 'Wrong', 'two')
    service.session.rollback()
    assert len(service.seating(lesson)['history']) == 1


@pytest.mark.parametrize('sql', [
    'UPDATE seat_assignments SET student_id=2', 'DELETE FROM seat_assignments',
    'UPDATE lesson_layouts SET layout_id=layout_id',
    "INSERT INTO seats(layout_id,label,x,y) SELECT layout_id,'Extra',0,0 FROM lesson_layouts",
])
def test_raw_guards(activity, sql):
    service, lesson = activity
    service.assign_seat(lesson, 1, service.seating(lesson)['seats'][0].id, 'Initial', 'one')
    service.session.commit()
    with pytest.raises(DBAPIError):
        service.session.execute(text(sql))
    service.session.rollback()


def test_behavior_correction_as_of(activity):
    service, lesson = activity
    category = service.create_category('Helping', 'positive')
    original = service.record_behavior(1, lesson, category.id, 'Helpful', 'teacher', 'event')
    before = original.occurred_at
    service.correct_behavior(original.id, 2, 'Wrong student')
    assert service.behavior_for_student(1) == []
    assert service.behavior_for_student(1, as_of=before)[0]['id'] == original.id
    row = service.behavior_for_student(2)[0]
    assert row['corrected'] and row['effective_student_id'] == 2
    assert row['occurred_at'].tzinfo is not None
    assert row['original_student_id'] == 1 and row['corrections'][0]['reason'] == 'Wrong student'
    assert service.session.get(BehaviorEvent, original.id).student_id == 1
    assert service.behavior_history(lesson)[0]['student_id'] == 1
    assert service.behavior_history(lesson)[0]['corrections'][0]['student_id'] == 2


def test_migration_and_pure_read(activity):
    service, lesson = activity
    service.session.commit()
    ensure_activity_schema(service.session.bind)
    assert service.seating(lesson)['layout'] is not None
    assert not service.session.new and not service.session.dirty


def test_stale_revision_and_fixed_roster(activity):
    service, lesson = activity
    seat = service.seating(lesson)['seats'][0]
    service.assign_seat(lesson, 1, seat.id, 'Initial', 'one')
    service.session.commit()
    with pytest.raises(DBAPIError):
        service.session.add(SeatAssignment(lesson_id=lesson, student_id=1, seat_id=None, reason='Stale', operation_key='stale'))
        service.session.flush()
    service.session.rollback()


def test_transfer_preserves_snapshot(activity):
    service, lesson = activity
    seat = service.seating(lesson)['seats'][0]
    row = service.assign_seat(lesson, 1, seat.id, 'Initial', 'initial')
    service.session.commit()
    student = service.session.get(Student, 1)
    other = Group(name='Other')
    service.session.add(other)
    service.session.flush()
    student.group_id = other.id
    service.session.commit()
    assert service.seating(lesson)['assignments'][0].id == row.id
    assert service.seating(lesson)['assignments'][0].seat_id == seat.id


def test_concurrent_occupancy(activity):
    from concurrent.futures import ThreadPoolExecutor
    service, lesson = activity
    seat_id = service.seating(lesson)['seats'][0].id
    service.session.commit()
    engine = service.session.bind
    def write(student):
        with Session(engine) as session:
            try:
                ActivityService(session).assign_seat(lesson, student, seat_id, 'Concurrent', f'concurrent-{student}')
                session.commit()
                return True
            except DBAPIError:
                session.rollback()
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, (1, 2))) == [False, True]
    assert len(service.seating(lesson)['assignments']) == 1


def test_closed_term(activity):
    from app.models import AcademicYear, AcademicTerm, Discipline, CourseOffering
    service, lesson_id = activity
    session = service.session
    year = AcademicYear(name='Year', start_date=date(2030, 1, 1), end_date=date(2031, 1, 1))
    discipline = Discipline(name='Class')
    session.add_all([year, discipline])
    session.flush()
    term = AcademicTerm(year_id=year.id, name='Term', start_date=date(2030, 1, 7), total_weeks=17, status='closed')
    session.add(term)
    session.flush()
    course = CourseOffering(term_id=term.id, discipline_id=discipline.id, name='Course')
    session.add(course)
    session.flush()
    lesson = session.get(Lesson, lesson_id)
    session.get(Schedule, lesson.schedule_id).offering_id = course.id
    category = service.create_category('Attention', 'negative')
    session.commit()
    with pytest.raises(DBAPIError):
        service.record_behavior(1, lesson_id, category.id, '', 'teacher', 'closed')
    session.rollback()


def test_orm_and_behavior_immutability(activity):
    service, lesson = activity
    item = service.record_typical_behavior(1, lesson, 'Helping others', 'default')
    service.session.commit()
    item.comment = 'Overwrite'
    with pytest.raises(DBAPIError):
        service.session.flush()
    service.session.rollback()
    assert service.behavior_for_student(1)[0]['comment'] == ''
    with pytest.raises(ActivityError):
        service.record_typical_behavior(2, lesson, 'Helping others', 'default')
    service.session.get(Lesson, lesson).participants_complete = True
    service.session.commit()
    with pytest.raises(DBAPIError):
        service.assign_seat(lesson, 2, service.seating(lesson)['seats'][0].id, 'Outside', 'outside')
    service.session.rollback()


def test_guard_installer_preserves_caller_transaction(activity):
    service, lesson = activity
    service.session.commit()
    with service.session.bind.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        connection.exec_driver_sql("INSERT INTO classrooms(name) VALUES ('Rolled back')")
        install_activity_guards(connection)
        assert connection.in_transaction()
        install_activity_guards(connection)
        connection.rollback()
    assert service.session.scalar(text("SELECT count(*) FROM classrooms WHERE name='Rolled back'")) == 0


def test_unattached_saved_version_is_sealed(activity):
    service, lesson = activity
    from app.models.journal_activity import Classroom, SeatingLayout
    room = service.session.scalar(select(Classroom))
    layout = service.create_layout(room.id, 'Unused', [dict(label='A', x=10, y=10)])
    service.session.commit()
    assert layout.sealed
    with pytest.raises(DBAPIError):
        service.session.execute(Seat.__table__.insert().values(layout_id=layout.id, label='Extra', x=0, y=0))
    service.session.rollback()
    assert service.session.get(SeatingLayout, layout.id).sealed


def test_behavior_recipient_timeline_preserves_grades(activity):
    from datetime import timedelta
    from app.models import Mark, AssessmentAttempt
    service, lesson = activity
    session = service.session
    session.add(Mark(student_id=1, lesson_id=lesson, data=7))
    session.commit()
    before = {table.name: list(session.execute(select(table)).mappings())
              for table in (Mark.__table__, AssessmentAttempt.__table__)}
    original = service.record_typical_behavior(1, lesson, 'Helping others', 'timeline')
    from app.models.journal_activity import BehaviorCorrection
    first = BehaviorCorrection(event_id=original.id, student_id=2, reason='Wrong recipient', source='teacher', occurred_at=original.occurred_at + timedelta(seconds=1))
    second = BehaviorCorrection(event_id=original.id, student_id=1, reason='Verified recipient', source='teacher', occurred_at=original.occurred_at + timedelta(seconds=2))
    session.add_all([first, second])
    session.flush()
    assert service.behavior_for_student(1, as_of=original.occurred_at)[0]['corrected'] is False
    assert service.behavior_for_student(1, as_of=first.occurred_at) == []
    assert service.behavior_for_student(2, as_of=first.occurred_at)[0]['effective_student_id'] == 2
    assert service.behavior_for_student(2, as_of=second.occurred_at) == []
    assert service.behavior_for_student(1, as_of=second.occurred_at)[0]['corrected'] is True
    after = {table.name: list(session.execute(select(table)).mappings())
             for table in (Mark.__table__, AssessmentAttempt.__table__)}
    assert before == after


def test_behavior_local_midnight(activity):
    from datetime import datetime, timezone, timedelta
    # Emulate the local calendar independently of the machine running pytest.
    class MoscowDateTime(datetime):
        def astimezone(self, tz=None):
            return super().astimezone(tz or timezone(timedelta(hours=3)))
    service, lesson = activity
    category = service.create_category('Midnight', 'positive')
    event = BehaviorEvent(student_id=1, lesson_id=lesson, category_id=category.id,
        comment='', source='teacher', operation_key='midnight',
        occurred_at=MoscowDateTime(2030, 1, 6, 21, 10, tzinfo=timezone.utc))
    service.session.add(event)
    service.session.flush()
    assert service.behavior_for_student(1, start_date=date(2030, 1, 7), end_date=date(2030, 1, 8))[0]['id'] == event.id
    assert service.behavior_for_student(1, start_date=date(2030, 1, 6), end_date=date(2030, 1, 7)) == []
