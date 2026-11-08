"""Full teaching archive regression tests; only temporary SQLite databases."""
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import select, update, text

from app.models import (Base, AcademicYear, AcademicTerm, Discipline, CourseOffering,
                        CourseOfferingGroup, TeachingModule, AssessmentEvent, Consultation,
                        ConsultationVisit, LabWork, ChecklistVersion, ChecklistCriterion,
                        AssessmentAttempt, CriterionAnswer, ResultCorrection, IndividualPlan,
                        PlanStage, PlanEntry, TeachingAudit, Schedule, ScheduleGroupLink,
                        Lesson, Attendance, AttendanceRevision, EventCancellation,
                        LessonDisposition, NonTeachingDay)
from app.ui.data import repository as repository_module
from app.ui.data.teaching_archive import export_archive, preview_archive, restore_archive


@pytest.fixture
def repositories(tmp_path, monkeypatch):
    opened = []
    def create():
        monkeypatch.setattr(repository_module, 'DATABASE_URL', f'sqlite:///{tmp_path / (str(len(opened)) + ".db")}')
        repo = repository_module.DiaryRepository()
        opened.append(repo)
        return repo
    yield create
    for repo in opened:
        repo.close()
        repo.engine.dispose()


def graph(repo):
    group = repo.create_group('=not a formula', None)
    student = repo.create_student(group, 'Name', 'Surname')
    now = datetime(2026, 9, 1, 10, 0, 0, 123456, timezone.utc)
    records = [
        AcademicYear(id=21, name='2026', start_date=date(2026, 1, 1), end_date=date(2027, 1, 1)),
        Discipline(id=22, name='Science'), Consultation(id=23, starts_at=now, title='Consult'),
    ]
    repo.session.add_all(records)
    repo.session.flush()
    repo.session.add(AcademicTerm(id=24, year_id=21, name='Autumn', start_date=date(2026, 8, 31), total_weeks=16))
    repo.session.flush()
    repo.session.add_all([CourseOffering(id=25, term_id=24, discipline_id=22, name='Course'),
                          ConsultationVisit(id=26, consultation_id=23, student_id=student.id, purpose='defense')])
    repo.session.flush()
    repo.session.add_all([CourseOfferingGroup(offering_id=25, group_id=group.id),
                          TeachingModule(id=27, offering_id=25, name='Module', position=1, start_date=date(2026, 8, 31), end_date=date(2026, 12, 21)),
                          IndividualPlan(id=28, student_id=student.id, offering_id=25, title='Project', kind='project')])
    repo.session.flush()
    repo.session.add_all([AssessmentEvent(id=29, module_id=27, title='Lab', category='lab', max_points=Decimal('10.25'), required=True, attempt_policy='best'),
                          PlanStage(id=30, plan_id=28, position=1, title='Start')])
    repo.session.flush()
    repo.session.add_all([LabWork(id=31, event_id=29, title='Lab'), PlanEntry(stage_id=30, completed=True, comment='', consultation_visit_id=26, occurred_at=now)])
    repo.session.flush()
    repo.session.add(ChecklistVersion(id=32, lab_id=31, revision=1))
    repo.session.flush()
    repo.session.add(ChecklistCriterion(id=33, version_id=32, position=1, label='Works'))
    repo.session.flush()
    repo.session.add(AssessmentAttempt(id=34, event_id=29, student_id=student.id, attempt_number=1,
        operation_key='attempt', occurred_at=now, work_completed=True, defended=True, passed=True,
        points=Decimal('8.25'), checklist_version_id=32, consultation_visit_id=26, question_passed=True))
    repo.session.flush()
    repo.session.add(CriterionAnswer(attempt_id=34, criterion_id=33, satisfied=True))
    repo.session.flush()
    repo.session.execute(update(AssessmentAttempt).where(AssessmentAttempt.id == 34).values(finalized=True))
    repo.session.add_all([ResultCorrection(attempt_id=34, points=Decimal('9.75'), passed=True, reason='Reviewed', source='teacher', operation_key='correction', occurred_at=now),
        TeachingAudit(action='test', entity_type='attempt', entity_id=34, reason='\\N', source='teacher', occurred_at=now)])
    repo.session.commit()
    schedule = Schedule(day=date.today().strftime('%A'), time=time(10), odd_or_even='even',
                        type='Seminar', is_assessment=True, effective_from=date.today())
    repo.session.add(schedule)
    repo.session.flush()
    repo.session.add(ScheduleGroupLink(schedule_id=schedule.id, group_id=group.id))
    repo.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=date.today(), topic='=Topic')
    repo.session.add(lesson)
    repo.session.commit()
    repo.complete_lesson_roster(lesson)
    repo.save_lesson_student_record(lesson, student, attended=True, comment_text='=Comment', mark_value=90)
    attendance = repo.session.scalar(select(Attendance).where(Attendance.lesson_id == lesson.id))
    repo.session.add(AssessmentEvent(id=39, module_id=27, title='Cancelled', category='additional',
                                    max_points=Decimal('1.00'), required=False, attempt_policy='latest'))
    repo.session.flush()
    repo.session.add_all([
        AttendanceRevision(attendance_id=attendance.id, status='present', reason='Recorded', source='teacher',
                           operation_key='attendance', occurred_at=now),
        EventCancellation(event_id=39, reason='Cancelled', occurred_at=now),
        LessonDisposition(lesson_id=lesson.id, status='held', reason='Held', occurred_at=now),
        NonTeachingDay(term_id=24, date=date(2026, 11, 4), reason='Holiday'),
    ])
    repo.session.commit()


def test_complete_graph_roundtrip_stable_ids_and_repeat_rejected(repositories, tmp_path):
    source, target = repositories(), repositories()
    graph(source)
    path = export_archive(source.session, tmp_path / 'full.xlsx')
    data = preview_archive(path)
    assert set(data) == set(Base.metadata.tables)
    assert data['assessment_attempts'][0]['points'] == Decimal('8.25')
    assert data['assessment_attempts'][0]['occurred_at'].microsecond == 123456
    assert data['teaching_audit'][0]['reason'] == '\\N'
    restore_archive(target, data)
    second = preview_archive(export_archive(target.session, tmp_path / 'second.xlsx'))
    assert second == data
    with pytest.raises(ValueError, match='empty database'):
        restore_archive(target, data)
    assert preview_archive(export_archive(target.session, tmp_path / 'third.xlsx')) == data
    wb = load_workbook(path)
    assert wb['groups']['A2'].data_type != 'f'
    wb.close()


def test_preview_ordinary_and_tampered_columns(repositories, tmp_path):
    path = tmp_path / 'ordinary.xlsx'
    Workbook().save(path)
    assert preview_archive(path) is None
    repo = repositories()
    graph(repo)
    export_archive(repo.session, path)
    wb = load_workbook(path)
    wb['assessment_attempts']['A1'] = 'tampered'
    wb.save(path)
    wb.close()
    with pytest.raises(ValueError, match='columns'):
        preview_archive(path)


def test_validation_and_transaction_rollback(repositories, tmp_path, monkeypatch):
    source, target = repositories(), repositories()
    graph(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'archive.xlsx'))
    invalid = deepcopy(data)
    invalid['assessment_attempts'][0]['points'] = Decimal('99.00')
    with pytest.raises(ValueError, match='limits'):
        restore_archive(target, invalid)
    original = target._validate_restored_history
    def fail():
        raise ValueError('forced rollback')
    monkeypatch.setattr(target, '_validate_restored_history', fail)
    with pytest.raises(ValueError, match='forced rollback'):
        restore_archive(target, data)
    assert all(target.session.scalar(select(t.c.id).limit(1)) is None for t in Base.metadata.tables.values())
    monkeypatch.setattr(target, '_validate_restored_history', original)
    # A successful retry proves transactional DDL restored all dropped triggers.
    restore_archive(target, data)


def test_repeated_migration_and_formula_and_nullable_tampering(repositories, tmp_path):
    from app.ui.data.membership_migration import ensure_membership_schema
    repo = repositories()
    graph(repo)
    before = preview_archive(export_archive(repo.session, tmp_path / 'before.xlsx'))
    repo.session.rollback()
    ensure_membership_schema(repo.engine)
    ensure_membership_schema(repo.engine)
    assert preview_archive(export_archive(repo.session, tmp_path / 'after.xlsx')) == before
    wb = load_workbook(tmp_path / 'before.xlsx')
    sheet = wb['assessment_attempts']
    column = [c.value for c in sheet[1]].index('points') + 1
    sheet.cell(2, column, '=1+2')
    wb.save(tmp_path / 'formula.xlsx')
    wb.close()
    with pytest.raises(ValueError, match='formula'):
        preview_archive(tmp_path / 'formula.xlsx')


def test_incomplete_checklist_rejected_without_database_changes(repositories, tmp_path):
    source, target = repositories(), repositories()
    graph(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'checklist.xlsx'))
    data['criterion_answers'].clear()
    with pytest.raises(ValueError, match='complete versioned checklist'):
        restore_archive(target, data)
    assert target.session.scalar(select(AssessmentAttempt.id).limit(1)) is None


def test_closed_term_and_legacy_unknown_roster_restore(repositories, tmp_path):
    source, target = repositories(), repositories()
    graph(source)
    source.session.execute(update(AcademicTerm).where(AcademicTerm.id == 24).values(status='closed'))
    source.session.commit()
    data = preview_archive(export_archive(source.session, tmp_path / 'closed.xlsx'))
    data['lessons'][0]['roster_completed_at'] = None
    data['lessons'][0]['roster_time_basis'] = 'unknown'
    restore_archive(target, data)
    restored = preview_archive(export_archive(target.session, tmp_path / 'restored.xlsx'))
    assert restored == data
    assert target.session.get(AcademicTerm, 24).status == 'closed'
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError, match='closed'):
        target.session.execute(Base.metadata.tables['non_teaching_days'].insert().values(
            term_id=24, date=date(2026, 11, 5), reason='must fail'))
    target.session.rollback()


def test_restore_archived_group_and_student_with_historical_offering(repositories, tmp_path):
    source, target = repositories(), repositories()
    graph(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'archived.xlsx'))
    yesterday = date.today() - timedelta(days=1)
    data['academic_terms'][0]['status'] = 'closed'
    data['groups'][0].update(is_archived=True, archive_reason='Finished')
    data['students'][0].update(status='archived', archived_at=date.today(), archive_reason='Finished')
    data['groupmemberships'][0].update(start_date=yesterday, end_date=date.today())
    data['lessons'][0]['date'] = yesterday
    data['schedules'][0].update(effective_from=yesterday, effective_until=date.today())
    restore_archive(target, data)
    assert preview_archive(export_archive(target.session, tmp_path / 'archived-restored.xlsx')) == data
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError, match='historical group links'):
        target.session.execute(ScheduleGroupLink.__table__.insert().values(
            group_id=data['groups'][0]['id'], schedule_id=data['schedules'][0]['id']))
    target.session.rollback()


def test_cancelled_seminar_slot_can_have_replacement(repositories, tmp_path):
    source, target = repositories(), repositories()
    graph(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'seminars.xlsx'))
    data['schedules'][0]['offering_id'] = 25
    lesson_id = data['lessons'][0]['id']
    event = dict(data['assessment_events'][0], id=100, category='seminar_start', lesson_id=lesson_id)
    data['assessment_events'].extend([event, dict(event, id=101)])
    data['event_cancellations'].append(dict(data['event_cancellations'][0], id=100, event_id=100))
    restore_archive(target, data)
    restored = preview_archive(export_archive(target.session, tmp_path / 'seminar-restored.xlsx'))
    assert restored == data


def test_revision_projection_replay_preserves_timestamps(repositories, tmp_path):
    source, target = repositories(), repositories()
    graph(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'projection.xlsx'))
    first = dict(data['attendance_revisions'][0], status='absent', arrived_at=None, late_seconds=None)
    data['attendance_revisions'] = [first, dict(first, id=100, status='present', operation_key='correction-present')]
    # The latest correction says present, but the actual arrival time is unknown.
    assert data['attendance_revisions'][-1]['arrived_at'] is None
    restore_archive(target, data)
    assert preview_archive(export_archive(target.session, tmp_path / 'projected.xlsx')) == data


def test_historical_cancellation_replay_is_independent_of_current_date(repositories, tmp_path):
    source, target = repositories(), repositories()
    graph(source)
    schedule = Schedule(day='Monday', time=time(12), odd_or_even='even', type='Seminar')
    source.session.add(schedule)
    source.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=date.today() + timedelta(days=2))
    source.session.add(lesson)
    source.session.commit()
    source.teaching_action('set_lesson_disposition', lesson_id=lesson.id, status='cancelled', reason='No class')
    data = preview_archive(export_archive(source.session, tmp_path / 'cancelled.xlsx'))
    with target.engine.begin() as connection:
        trigger = connection.execute(text("SELECT sql FROM sqlite_master WHERE name='education_lesson_dispositions_insert'")).scalar_one()
        connection.exec_driver_sql('DROP TRIGGER education_lesson_dispositions_insert')
        connection.exec_driver_sql(trigger.replace("date('now','localtime')", "'2100-01-01'"))
    restore_archive(target, data)
    assert preview_archive(export_archive(target.session, tmp_path / 'cancelled-restored.xlsx')) == data
    with target.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM sqlite_master WHERE name='education_lesson_dispositions_insert'")).scalar_one() == 1


@pytest.mark.parametrize('tampering, message', [
    ('missing_lab', 'lab work'), ('incomplete_work', 'completed work'),
    ('module_overlap', 'overlap'), ('foreign_student', 'eligible'),
    ('duplicate_seminar', 'unique lesson slot'), ('utc_missing_time', 'timestamp'),
    ('missing_schedule_groups', 'missing groups'),
    ('attempt_gap', 'sequence has gaps'),
    ('pending', 'unfinalized'), ('failed_lab_correction', 'new defense'),
    ('late_without_arrival', 'arrival and known UTC'),
    ('late_unknown_basis', 'arrival and known UTC'),
    ('disposition_after_move', 'subsequent dispositions'),
])
def test_reject_unsafe_graphs(repositories, tmp_path, tampering, message):
    source, target = repositories(), repositories()
    graph(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'unsafe.xlsx'))
    if tampering == 'missing_lab':
        data['lab_works'].clear()
        data['checklist_versions'].clear()
        data['checklist_criteria'].clear()
        data['criterion_answers'].clear()
        data['assessment_attempts'][0]['checklist_version_id'] = None
    elif tampering == 'incomplete_work':
        data['assessment_attempts'][0]['work_completed'] = False
    elif tampering == 'module_overlap':
        data['teaching_modules'].append(dict(data['teaching_modules'][0], id=100, position=2))
    elif tampering == 'foreign_student':
        data['course_offering_groups'].clear()
    elif tampering == 'duplicate_seminar':
        event = dict(data['assessment_events'][0], category='seminar_start', lesson_id=data['lessons'][0]['id'])
        # Supply matching academic context so the duplicate-slot check is exercised.
        data['schedules'][0]['offering_id'] = 25
        data['assessment_events'].extend([dict(event, id=100), dict(event, id=101)])
    elif tampering == 'utc_missing_time':
        data['lessons'][0]['roster_time_basis'] = 'utc'
        data['lessons'][0]['roster_completed_at'] = None
    elif tampering == 'attempt_gap':
        data['assessment_attempts'][0]['attempt_number'] = 2
    elif tampering == 'pending':
        data['assessment_attempts'][0]['finalized'] = False
    elif tampering == 'failed_lab_correction':
        data['assessment_attempts'][0].update(passed=False, points=Decimal('0.00'))
    elif tampering == 'late_without_arrival':
        data['attendance_revisions'][0].update(status='late', arrived_at=None, late_seconds=10)
    elif tampering == 'late_unknown_basis':
        data['lessons'][0]['roster_time_basis'] = 'unknown'
        data['attendance_revisions'][0].update(status='late', arrived_at=datetime.now(timezone.utc), late_seconds=10)
    elif tampering == 'disposition_after_move':
        data['lesson_dispositions'].append(dict(data['lesson_dispositions'][0], id=100))
        data['lesson_dispositions'][0]['status'] = 'moved'
    else:
        data['schedules'][0]['offering_id'] = 25
        data['schedulegrouplinks'].clear()
    with pytest.raises(ValueError, match=message):
        restore_archive(target, data)
    assert target.session.scalar(select(AcademicTerm.id).limit(1)) is None
