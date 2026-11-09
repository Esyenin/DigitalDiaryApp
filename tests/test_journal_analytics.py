"""Canonical journal views must not mix grading scales or rewrite history."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import (AssessmentEvent, Attendance, AttendanceRevision, Lesson,
                        LessonParticipant, Mark, Schedule, ScheduleGroupLink)
from app.services.journal_analytics import JournalAnalytics
from app.ui.data import repository as repository_module


@pytest.fixture
def journal(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, 'DATABASE_URL', f"sqlite:///{tmp_path / 'journal.db'}")
    repo = repository_module.DiaryRepository()
    monday = date.today() - timedelta(days=date.today().weekday(), weeks=2)
    year = repo.academic_action('create_year', 'Year', monday, monday + timedelta(weeks=52))
    term = repo.academic_action('create_term', year.id, 'Term', monday, 17)
    groups = [repo.create_group(name, None) for name in ('Old', 'New')]
    students = [repo.create_student(groups[0], name, 'Student') for name in ('Anna', 'Boris')]
    discipline = repo.academic_action('create_discipline', 'Programming')
    course = repo.academic_action('create_offering', term.id, discipline.id, 'Shared', [row.id for row in groups])
    module = repo.academic_action('create_module', course.id, 'Module', 1, monday, monday + timedelta(weeks=17))
    yield repo, term, course, module, groups, students
    repo.close()
    repo.engine.dispose()


def make_lesson(repo, course, groups, day=None):
    schedule = Schedule(offering_id=course.id, day='Monday', time=time(10), type='Seminar', odd_or_even='even')
    repo.session.add(schedule)
    repo.session.flush()
    repo.session.add_all([ScheduleGroupLink(schedule_id=schedule.id, group_id=row.id) for row in groups])
    repo.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=day or date.today())
    repo.session.add(lesson)
    repo.session.commit()
    return lesson


def test_seminar_without_lesson_rejected_in_service_and_sql(journal):
    repo, term, course, module, groups, students = journal
    values = dict(module_id=module.id,title='Test',category='seminar_start',max_points=5,required=True,attempt_policy='best')
    with pytest.raises(repository_module.RepositoryError, match='lesson'):
        repo.teaching_action('create_event', **values)
    with pytest.raises(IntegrityError, match='lesson'):
        repo.session.add(AssessmentEvent(**values))
        repo.session.flush()
    repo.session.rollback()
    assert not list(repo.session.scalars(select(AssessmentEvent)))


def test_old_card_and_direct_sql_cannot_insert_future_attendance(journal):
    repo, term, course, module, groups, students = journal
    lesson = make_lesson(repo, course, groups, date.today() + timedelta(days=1))
    with pytest.raises(repository_module.RepositoryError, match='future'):
        repo.save_lesson_student_record(lesson, students[0], attended=True, comment_text='future', mark_value=5)
    assert not list(repo.session.scalars(select(Attendance)))
    assert not list(repo.session.scalars(select(LessonParticipant)))
    with pytest.raises(IntegrityError, match='future'):
        repo.session.add(Attendance(lesson_id=lesson.id,student_id=students[0].id,is_visited=True))
        repo.session.flush()
    repo.session.rollback()
    assert not list(repo.session.scalars(select(AttendanceRevision)))


def test_new_points_legacy_marks_and_excused_absence_stay_separate(journal):
    repo, term, course, module, groups, students = journal
    lesson = make_lesson(repo, course, groups)
    repo.complete_lesson_roster(lesson)
    event = repo.teaching_action('create_event', module_id=module.id, title='Exam', category='checkpoint',
                                 max_points=100, required=True, attempt_policy='best')
    repo.teaching_action('record_attempt', event_id=event.id, student_id=students[0].id, points=85,
                         passed=True,work_completed=True,defended=False,operation_key=uuid4().hex)
    repo.teaching_action('record_attendance', lesson_id=lesson.id,student_id=students[0].id,status='excused',
                         reason='Medical confirmation',operation_key=uuid4().hex)
    repo.session.add(Mark(lesson_id=lesson.id,student_id=students[0].id,data=99))
    repo.session.commit()
    before = repo.session.scalar(text('SELECT total_changes()'))
    data = JournalAnalytics(repo.session).student(students[0].id, term_id=term.id)
    assert data['courses'][0]['earned'] == Decimal(85)
    assert data['courses'][0]['excellent']
    assert data['legacy_marks'][0]['value'] == 99
    assert data['attendance']['excused'] == 1
    assert data['attendance']['present'] == data['attendance']['absent'] == 0
    assert data['attendance']['percentage'] == Decimal('0.00')
    assert repo.session.scalar(text('SELECT total_changes()')) == before
    group = JournalAnalytics(repo.session).group(groups[0].id,term_id=term.id)
    assert group['courses'][0]['average'] == Decimal('85.00')
    assert group['courses'][0]['observed'] == 1
    assert group['debtors_count'] == 1


def test_non100_scale_is_not_normalized_or_called_excellent(journal):
    repo, term, course, module, groups, students = journal
    event = repo.teaching_action('create_event', module_id=module.id,title='Work',category='additional',
                                 max_points=120,required=True,attempt_policy='latest')
    repo.teaching_action('record_attempt',event_id=event.id,student_id=students[0].id,points=100,passed=True,
                         work_completed=True,defended=False,operation_key=uuid4().hex)
    data = JournalAnalytics(repo.session).offering(course.id)
    row = next(row for row in data['students'] if row['id'] == students[0].id)['courses'][0]
    assert row['earned'] == 100 and row['maximum'] == 120
    assert not row['scale100'] and not row['excellent']


def test_one_legacy_record_does_not_obscure_other_fixed_participants(journal):
    repo, term, course, module, groups, students = journal
    lesson = make_lesson(repo, course, groups)
    repo.session.add(Attendance(lesson_id=lesson.id, student_id=students[0].id, is_visited=True))
    repo.session.commit()
    repo.complete_lesson_roster(lesson)
    counts = repo.lesson_attendance_counts(lesson)
    assert counts['present'] == 1
    assert counts['absent'] == 1
    assert counts['unknown'] == 0
    assert counts['rate'] == '-'


def test_fixed_history_survives_transfer_and_archive(journal):
    repo, term, course, module, groups, students = journal
    lesson = make_lesson(repo, course, groups)
    repo.complete_lesson_roster(lesson)
    repo.teaching_action('record_attendance',lesson_id=lesson.id,student_id=students[0].id,status='present',
                         mode='correction',reason='Confirmed on time',operation_key=uuid4().hex)
    repo.transfer_student(students[0], groups[1], date.today())
    repo.archive_student(students[0],reason='Graduated')
    data = JournalAnalytics(repo.session).group(groups[0].id,term_id=term.id)
    assert students[0].id in {row['id'] for row in data['students']}
    original = next(row for row in data['students'] if row['id'] == students[0].id)
    assert original['attendance']['present'] == 1
    assert original['status'] == 'archived'
    assert repo.session.scalar(select(LessonParticipant.group_id).where(
        LessonParticipant.lesson_id==lesson.id,LessonParticipant.student_id==students[0].id)) == groups[0].id


def test_as_of_uses_attempt_and_correction_history(journal):
    repo, term, course, module, groups, students = journal
    yesterday = date.today() - timedelta(days=1)
    stamp = datetime.combine(yesterday, time(10), tzinfo=timezone.utc)
    event = AssessmentEvent(module_id=module.id,title='Snapshot',category='checkpoint',max_points=100,
                            required=True,attempt_policy='best',created_at=stamp,configured_at=stamp)
    repo.session.add(event)
    repo.session.commit()
    attempt = repo.teaching_action('record_attempt',event_id=event.id,student_id=students[0].id,points=70,passed=True,
        work_completed=True,defended=False,operation_key=uuid4().hex,occurred_at=stamp)
    repo.teaching_action('correct_result',attempt_id=attempt.id,points=90,passed=True,reason='Reviewed today',operation_key=uuid4().hex)
    old = JournalAnalytics(repo.session).student(students[0].id,term_id=term.id,as_of=yesterday)
    new = JournalAnalytics(repo.session).student(students[0].id,term_id=term.id)
    assert old['courses'][0]['earned'] == 70
    assert new['courses'][0]['earned'] == 90


def test_group_rows_and_total_use_same_historical_attendance_scope(journal):
    repo, term, course, module, groups, students = journal
    first = make_lesson(repo,course,[groups[0]])
    repo.complete_lesson_roster(first)
    repo.teaching_action('record_attendance',lesson_id=first.id,student_id=students[0].id,status='present',
        mode='correction',reason='Present in old group',operation_key=uuid4().hex)
    repo.transfer_student(students[0],groups[1],date.today())
    second = make_lesson(repo,course,[groups[1]])
    repo.teaching_action('record_attendance',lesson_id=second.id,student_id=students[0].id,status='present',
        mode='correction',reason='Present in new group',operation_key=uuid4().hex)
    analytics = JournalAnalytics(repo.session)
    original = analytics.group(groups[0].id,term_id=term.id)
    row = next(item for item in original['students'] if item['id']==students[0].id)
    assert row['attendance']['present'] == 1
    assert original['attendance']['present'] == 1
    assert analytics.student(students[0].id,term_id=term.id)['attendance']['present'] == 2


def test_legacy_marks_obey_course_filter_and_unassigned_remain_separate(journal):
    repo, term, course, module, groups, students = journal
    current = make_lesson(repo,course,groups)
    repo.session.add(Mark(lesson_id=current.id,student_id=students[0].id,data=77))
    repo.session.commit()
    analytics = JournalAnalytics(repo.session)
    assert analytics.student(students[0].id)['legacy_marks'][0]['value'] == 77
    assert not analytics.student(students[0].id,offering_ids=[])['legacy_marks']
    assert len(analytics.student(students[0].id,offering_ids=[course.id])['legacy_marks']) == 1


def test_snapshot_uses_explicit_utc_configuration_not_naive_base_clock(journal):
    from app.services.teaching import TeachingService
    repo, term, course, module, groups, students = journal
    configured = datetime.combine(date.today(),time(20,30),tzinfo=timezone.utc)
    event = AssessmentEvent(module_id=module.id,title='UTC configuration',category='checkpoint',max_points=100,
        required=True,attempt_policy='best',configured_at=configured,
        created_at=configured.astimezone().replace(tzinfo=None))
    repo.session.add(event)
    repo.session.commit()
    result = TeachingService(repo.session).summary(course.id,students[0].id,as_of=date.today())
    assert result['maximum'] == Decimal(100)
