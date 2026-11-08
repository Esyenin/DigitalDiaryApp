"""Direct database writes must obey the same history rules as services."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import DBAPIError

from app.models import (Base, AcademicYear, AcademicTerm, Discipline, CourseOffering,
                        CourseOfferingGroup, TeachingModule, AssessmentEvent,
                        AssessmentAttempt, Group, Student, GroupMembership)
from app.ui.data.academic_migration import ensure_academic_schema


@pytest.fixture
def education_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test_education.db'}")
    @event.listens_for(engine, "connect")
    def foreign_keys(dbapi, _):
        dbapi.execute("PRAGMA foreign_keys=ON")
    ensure_academic_schema(engine)
    seed_education(engine)
    yield engine
    engine.dispose()


def seed_education(engine):
    with engine.begin() as c:
        c.execute(AcademicYear.__table__.insert(), dict(id=1, name="Year", start_date=date(2026, 1, 1), end_date=date(2027, 1, 1)))
        c.execute(AcademicTerm.__table__.insert(), dict(id=1, year_id=1, name="Term", start_date=date(2026, 1, 5), total_weeks=20))
        c.execute(Discipline.__table__.insert(), dict(id=1, name="Discipline"))
        c.execute(Group.__table__.insert(), dict(id=1, name="A"))
        c.execute(Student.__table__.insert(), dict(id=1, group_id=1, surname="Student", first_name="One"))
        c.execute(GroupMembership.__table__.insert(), dict(student_id=1, group_id=1, start_date=date(2026, 1, 1), known_from=date(2026, 1, 1), origin="recorded"))
        c.execute(CourseOffering.__table__.insert(), dict(id=1, term_id=1, discipline_id=1, name="Course"))
        c.execute(CourseOfferingGroup.__table__.insert(), dict(offering_id=1, group_id=1))
        c.execute(TeachingModule.__table__.insert(), dict(id=1, offering_id=1, name="Module", position=1, start_date=date(2026, 1, 5), end_date=date(2026, 3, 1)))
        c.execute(AssessmentEvent.__table__.insert(), dict(id=1, module_id=1, title="Exam", category="checkpoint", max_points=10, required=True, attempt_policy="best", max_attempts=2))


def attempt(c, *, finalize=True, **overrides):
    values = dict(id=1, event_id=1, student_id=1, attempt_number=1, operation_key="one",
                  occurred_at=datetime(2026, 2, 1, tzinfo=timezone.utc), work_completed=True,
                  defended=True, passed=True, points=5)
    values.update(overrides)
    c.execute(AssessmentAttempt.__table__.insert(), values)
    if finalize:
        c.execute(AssessmentAttempt.__table__.update().where(
            AssessmentAttempt.id == values["id"]).values(finalized=True))


@pytest.mark.parametrize("sql", [
    "UPDATE assessment_events SET max_points=20 WHERE id=1",
    "DELETE FROM assessment_events WHERE id=1",
    "DELETE FROM academic_terms WHERE id=1",
    "UPDATE teaching_modules SET name='Changed' WHERE id=1",
    "DELETE FROM course_offering_groups",
])
def test_configuration_history_immutable(education_engine, sql):
    with education_engine.begin() as c:
        with pytest.raises(DBAPIError, match="immutable"):
            c.exec_driver_sql(sql)


def test_locking_noop_and_valid_attempt(education_engine):
    with education_engine.begin() as c:
        c.exec_driver_sql("UPDATE assessment_events SET id=id WHERE id=1")
        attempt(c)
        c.exec_driver_sql("UPDATE assessment_attempts SET id=id WHERE id=1")
        with pytest.raises(DBAPIError, match="immutable"):
            c.exec_driver_sql("UPDATE assessment_attempts SET points=6 WHERE id=1")


@pytest.mark.parametrize("values", [dict(points=11), dict(attempt_number=3), dict(student_id=2)])
def test_attempt_bounds_and_eligibility(education_engine, values):
    with education_engine.begin() as c:
        with pytest.raises(DBAPIError):
            attempt(c, **values)


def test_cancellation_cannot_erase_earned_score(education_engine):
    from app.models import EventCancellation
    with education_engine.begin() as c:
        attempt(c)
        with pytest.raises(DBAPIError, match="with attempts"):
            c.execute(EventCancellation.__table__.insert(), dict(event_id=1, reason="Cancelled"))
        assert c.scalar(select(AssessmentAttempt.points)) == 5


def test_cancelled_event_rejects_attempt(education_engine):
    from app.models import EventCancellation
    with education_engine.begin() as c:
        c.execute(EventCancellation.__table__.insert(), dict(event_id=1, reason="Cancelled"))
        with pytest.raises(DBAPIError, match="cancelled"):
            attempt(c)


def test_closed_term_blocks_results_but_allows_selection(education_engine):
    with education_engine.begin() as c:
        c.exec_driver_sql("UPDATE academic_terms SET status='closed' WHERE id=1")
        with pytest.raises(DBAPIError, match="closed"):
            attempt(c)
        c.exec_driver_sql("INSERT INTO academic_selection (id, term_id) VALUES (1,1)")
        with pytest.raises(DBAPIError, match="immutable"):
            c.exec_driver_sql("UPDATE academic_terms SET status='open' WHERE id=1")


@pytest.mark.parametrize("start,end", [(date(2026, 2, 1), date(2026, 4, 1)), (date(2025, 12, 1), date(2026, 1, 2))])
def test_module_ranges_and_overlap(education_engine, start, end):
    with education_engine.begin() as c:
        with pytest.raises(DBAPIError, match="overlap|outside"):
            c.execute(TeachingModule.__table__.insert(), dict(offering_id=1, position=2, name="Bad", start_date=start, end_date=end))


def test_criterion_must_match_attempt_version(education_engine):
    from app.models import CriterionAnswer
    with education_engine.begin() as c:
        attempt(c, finalize=False)
        with pytest.raises(DBAPIError, match="criterion"):
            c.execute(CriterionAnswer.__table__.insert(), dict(attempt_id=1, criterion_id=999, satisfied=True))


def test_failed_transaction_rolls_back_new_results(education_engine):
    with pytest.raises(DBAPIError):
        with education_engine.begin() as c:
            attempt(c)
            c.exec_driver_sql("DELETE FROM assessment_attempts")
    with education_engine.connect() as c:
        assert c.scalar(select(AssessmentAttempt.id)) is None


def test_attendance_projection_only_accepts_latest_revision(education_engine):
    from datetime import time
    from app.models import Schedule, Lesson, Attendance, AttendanceRevision
    with education_engine.begin() as c:
        c.execute(Schedule.__table__.insert(), dict(id=1, day="Monday", time=time(10), type="Seminar", odd_or_even="even"))
        c.execute(Lesson.__table__.insert(), dict(id=1, schedule_id=1, date=date(2026, 2, 2)))
        c.execute(Attendance.__table__.insert(), dict(id=1, lesson_id=1, student_id=1, is_visited=False))
        c.execute(AttendanceRevision.__table__.insert(), dict(attendance_id=1, status="present", reason="Correction", source="teacher", operation_key="attendance-one"))
        assert c.scalar(select(Attendance.is_visited)) is True
        c.exec_driver_sql("UPDATE attendances SET is_visited=1 WHERE id=1")
        with pytest.raises(DBAPIError, match="projection"):
            c.exec_driver_sql("UPDATE attendances SET is_visited=0 WHERE id=1")
        with pytest.raises(DBAPIError, match="cannot be deleted"):
            c.exec_driver_sql("DELETE FROM attendances WHERE id=1")


def test_revision_insert_uses_latest_id_and_preserves_original_timestamp(education_engine):
    from datetime import time
    from app.models import Schedule, Lesson, Attendance, AttendanceRevision
    with education_engine.begin() as c:
        c.execute(Schedule.__table__.insert(), dict(id=1, day="Monday", time=time(10), type="Seminar", odd_or_even="even"))
        c.execute(Lesson.__table__.insert(), dict(id=1, schedule_id=1, date=date(2026, 2, 2)))
        c.execute(Attendance.__table__.insert(), dict(id=1, lesson_id=1, student_id=1, is_visited=False))
        before = c.scalar(select(Attendance.updated_at))
        c.execute(AttendanceRevision.__table__.insert(), dict(id=20, attendance_id=1, status="present", reason="New", source="teacher", operation_key="new"))
        assert c.scalar(select(Attendance.is_visited)) is True
        c.execute(AttendanceRevision.__table__.insert(), dict(id=10, attendance_id=1, status="absent", reason="Old", source="teacher", operation_key="old"))
        assert c.scalar(select(Attendance.is_visited)) is True
        assert c.scalar(select(Attendance.updated_at)) == before


@pytest.mark.parametrize("protection", ["roster", "participant", "attendance", "mark", "comment", "past", "held", "assessment"])
@pytest.mark.parametrize("status", ["cancelled", "holiday", "moved"])
def test_direct_disposition_cannot_hide_protected_lesson(education_engine, protection, status):
    from datetime import time, timedelta
    from app.models import Schedule, Lesson, LessonDisposition, LessonParticipant, Attendance, Mark, Comment
    with education_engine.begin() as c:
        c.execute(Schedule.__table__.insert(), dict(id=1, day="Monday", time=time(10), type="Seminar", odd_or_even="even"))
        day = date.today() - timedelta(days=1) if protection == "past" else date.today()
        c.execute(Lesson.__table__.insert(), dict(id=1, schedule_id=1, date=day, participants_complete=protection == "roster"))
        if protection == "participant":
            c.execute(LessonParticipant.__table__.insert(), dict(lesson_id=1, student_id=1, source="evidence"))
        if protection in {"attendance", "mark", "comment"}:
            model, values = {"attendance": (Attendance, dict(is_visited=True)), "mark": (Mark, dict(data=5)), "comment": (Comment, dict(data="Evidence"))}[protection]
            c.execute(model.__table__.insert(), dict(lesson_id=1, student_id=1, **values))
        if protection == "held":
            c.execute(LessonDisposition.__table__.insert(), dict(lesson_id=1, status="held", reason="Conducted"))
        if protection == "assessment":
            # Existing academic evidence can predate installation of guards.
            c.exec_driver_sql("DROP TRIGGER education_assessment_events_update")
            c.exec_driver_sql("UPDATE assessment_events SET lesson_id=1 WHERE id=1")
            attempt(c)
        with pytest.raises(DBAPIError, match="conducted or filled"):
            c.execute(LessonDisposition.__table__.insert(), dict(lesson_id=1, status=status, reason="Hide"))


def test_moved_source_cannot_receive_more_dispositions(education_engine):
    from datetime import time, timedelta
    from app.models import Schedule, Lesson, LessonDisposition
    with education_engine.begin() as c:
        c.execute(Schedule.__table__.insert(), dict(id=1, day="Monday", time=time(10), type="Seminar", odd_or_even="even"))
        c.execute(Lesson.__table__.insert(), dict(id=1, schedule_id=1, date=date.today() + timedelta(days=2)))
        c.execute(LessonDisposition.__table__.insert(), dict(lesson_id=1, status="moved", reason="Moved"))
        with pytest.raises(DBAPIError, match="already moved"):
            c.execute(LessonDisposition.__table__.insert(), dict(lesson_id=1, status="cancelled", reason="Cancel"))


@pytest.mark.parametrize("finalized,new_date", [(False, date(2026, 3, 2)), (True, date(2026, 2, 3))])
def test_direct_lesson_move_preserves_assessment_context(education_engine, finalized, new_date):
    from datetime import time
    from app.models import Schedule, Lesson
    with education_engine.begin() as c:
        c.execute(Schedule.__table__.insert(), dict(id=1, offering_id=1, day="Monday", time=time(10), type="Seminar", odd_or_even="even"))
        c.execute(Lesson.__table__.insert(), dict(id=1, schedule_id=1, date=date(2026, 2, 2)))
        c.execute(AssessmentEvent.__table__.insert(), dict(id=2, module_id=1, lesson_id=1, title="Linked", category="checkpoint", max_points=10, required=True, attempt_policy="best"))
        if finalized:
            attempt(c, event_id=2)
        with pytest.raises(DBAPIError, match="assessment"):
            c.execute(Lesson.__table__.update().where(Lesson.id == 1).values(date=new_date))
        assert c.scalar(select(Lesson.date)) == date(2026, 2, 2)


def test_group_archive_respects_open_academic_courses(education_engine):
    with education_engine.begin() as c:
        c.execute(Group.__table__.insert(), dict(id=2, name="Course-only group"))
        c.execute(CourseOfferingGroup.__table__.insert(), dict(offering_id=1, group_id=2))
        with pytest.raises(DBAPIError, match="open academic course"):
            c.exec_driver_sql("UPDATE groups SET is_archived=TRUE WHERE id=2")
        c.exec_driver_sql("UPDATE academic_terms SET status='closed' WHERE id=1")
        c.exec_driver_sql("UPDATE groups SET is_archived=TRUE WHERE id=2")


def test_new_group_cannot_change_used_offering(education_engine):
    from datetime import time
    from app.models import Schedule
    with education_engine.begin() as c:
        c.execute(Schedule.__table__.insert(), dict(id=1, offering_id=1, day="Monday", time=time(10), type="Seminar", odd_or_even="even"))
        c.execute(Group.__table__.insert(), dict(id=2, name="B"))
        with pytest.raises(DBAPIError, match="group set is immutable"):
            c.execute(CourseOfferingGroup.__table__.insert(), dict(offering_id=1, group_id=2))


def test_audit_is_append_only(education_engine):
    from app.models import TeachingAudit
    with education_engine.begin() as c:
        c.execute(TeachingAudit.__table__.insert(), dict(action="record", entity_type="assessment_attempts", entity_id=1, reason="Manual", source="teacher"))
        with pytest.raises(DBAPIError, match="immutable"):
            c.exec_driver_sql("DELETE FROM teaching_audit")


def test_prior_result_keeps_archived_same_day_student_eligible(education_engine):
    """A result is evidence even when a later same-day exit empties the period."""
    with education_engine.begin() as c:
        attempt(c)
        c.exec_driver_sql("UPDATE groupmemberships SET start_date='2026-02-01', end_date='2026-02-01' WHERE student_id=1")
        c.exec_driver_sql("UPDATE students SET status='archived', archived_at='2026-02-01' WHERE id=1")
        attempt(c, id=2, attempt_number=2, operation_key="after-exit")
        assert list(c.scalars(select(AssessmentAttempt.id).order_by(AssessmentAttempt.id))) == [1, 2]


def test_prior_result_in_other_offering_does_not_grant_eligibility(education_engine):
    with education_engine.begin() as c:
        attempt(c)
        c.execute(CourseOffering.__table__.insert(), dict(id=2, term_id=1, discipline_id=1, name="Other course"))
        c.execute(TeachingModule.__table__.insert(), dict(id=2, offering_id=2, name="Other module", position=1, start_date=date(2026, 1, 5), end_date=date(2026, 3, 1)))
        c.execute(AssessmentEvent.__table__.insert(), dict(id=2, module_id=2, title="Other exam", category="checkpoint", max_points=10, required=True, attempt_policy="best"))
        with pytest.raises(DBAPIError, match="not eligible"):
            attempt(c, id=2, event_id=2, operation_key="wrong-course")


def test_empty_same_day_membership_without_evidence_is_not_eligibility(education_engine):
    with education_engine.begin() as c:
        c.exec_driver_sql("UPDATE groupmemberships SET start_date='2026-02-01', end_date='2026-02-01' WHERE student_id=1")
        with pytest.raises(DBAPIError, match="not eligible"):
            attempt(c)


def test_direct_result_after_same_day_transfer_uses_membership_history(education_engine):
    with education_engine.begin() as c:
        c.execute(Group.__table__.insert(), dict(id=2, name="Transfer destination"))
        c.exec_driver_sql("UPDATE groupmemberships SET end_date='2026-02-01' WHERE student_id=1")
        c.execute(GroupMembership.__table__.insert(), dict(student_id=1, group_id=2, start_date=date(2026, 2, 1), known_from=date(2026, 2, 1), origin="recorded"))
        c.exec_driver_sql("UPDATE students SET group_id=2 WHERE id=1")
        attempt(c)
        assert c.scalar(select(AssessmentAttempt.student_id)) == 1


@pytest.mark.parametrize("start,weeks,reason", [
    (date(2026, 1, 6), 10, "Monday"),
    (date(2025, 12, 29), 10, "outside academic year"),
    (date(2026, 12, 28), 2, "outside academic year"),
])
def test_direct_term_insert_checks_calendar(education_engine, start, weeks, reason):
    with education_engine.begin() as c:
        with pytest.raises(DBAPIError, match=reason):
            c.execute(AcademicTerm.__table__.insert(), dict(year_id=1, name="Invalid", start_date=start, total_weeks=weeks))


def test_closed_term_history_reads_do_not_write(education_engine):
    with education_engine.begin() as c:
        attempt(c)
        c.exec_driver_sql("UPDATE academic_terms SET status='closed' WHERE id=1")
    with education_engine.connect() as c:
        before = c.exec_driver_sql("SELECT total_changes()").scalar()
        assert c.scalar(select(AssessmentAttempt.points)) == 5
        assert c.scalar(select(AcademicTerm.status)) == "closed"
        assert c.exec_driver_sql("SELECT total_changes()").scalar() == before


def lab_checklist(c, *, empty=False):
    from app.models import LabWork, ChecklistVersion, ChecklistCriterion
    c.execute(AssessmentEvent.__table__.insert(), dict(id=2, module_id=1, title="Lab", category="lab", max_points=10, required=True, attempt_policy="best"))
    c.execute(LabWork.__table__.insert(), dict(id=1, event_id=2, title="Lab"))
    c.execute(ChecklistVersion.__table__.insert(), dict(id=1, lab_id=1, revision=1))
    if not empty:
        c.execute(ChecklistCriterion.__table__.insert(), dict(id=1, version_id=1, position=1, label="Correct solution"))


@pytest.mark.parametrize("empty", [False, True])
def test_raw_successful_lab_cannot_finalize_without_answers(education_engine, empty):
    with education_engine.begin() as c:
        lab_checklist(c, empty=empty)
        attempt(c, event_id=2, checklist_version_id=1, question_passed=True, finalize=False)
        with pytest.raises(DBAPIError, match="complete and nonempty"):
            c.exec_driver_sql("UPDATE assessment_attempts SET finalized=TRUE WHERE id=1")
        assert not c.scalar(select(AssessmentAttempt.finalized))


def test_complete_lab_finalizes_once_and_freezes_answers(education_engine):
    from app.models import CriterionAnswer
    with education_engine.begin() as c:
        lab_checklist(c)
        attempt(c, event_id=2, checklist_version_id=1, question_passed=True, finalize=False)
        c.execute(CriterionAnswer.__table__.insert(), dict(attempt_id=1, criterion_id=1, satisfied=True))
        c.exec_driver_sql("UPDATE assessment_attempts SET finalized=TRUE WHERE id=1")
        c.exec_driver_sql("UPDATE assessment_attempts SET id=id WHERE id=1")
        with pytest.raises(DBAPIError, match="immutable"):
            c.exec_driver_sql("UPDATE assessment_attempts SET finalized=FALSE WHERE id=1")
        with pytest.raises(DBAPIError, match="immutable"):
            c.exec_driver_sql("UPDATE assessment_attempts SET finalized=TRUE, comment='Changed' WHERE id=1")
        with pytest.raises(DBAPIError, match="immutable"):
            c.execute(CriterionAnswer.__table__.insert(), dict(attempt_id=1, criterion_id=1, satisfied=True))


def test_false_criterion_cannot_finalize_passed_lab(education_engine):
    from app.models import CriterionAnswer
    with education_engine.begin() as c:
        lab_checklist(c)
        attempt(c, event_id=2, checklist_version_id=1, question_passed=True, finalize=False)
        c.execute(CriterionAnswer.__table__.insert(), dict(attempt_id=1, criterion_id=1, satisfied=False))
        with pytest.raises(DBAPIError, match="all criteria"):
            c.exec_driver_sql("UPDATE assessment_attempts SET finalized=TRUE WHERE id=1")


def test_insert_cannot_skip_draft_stage(education_engine):
    with education_engine.begin() as c:
        with pytest.raises(DBAPIError, match="draft"):
            attempt(c, finalized=True)


def test_correction_requires_finalized_attempt(education_engine):
    from app.models import ResultCorrection
    with education_engine.begin() as c:
        attempt(c, finalize=False)
        with pytest.raises(DBAPIError, match="unfinished"):
            c.execute(ResultCorrection.__table__.insert(), dict(attempt_id=1, points=6, passed=True, reason="Fix", source="teacher", operation_key="correction"))


def test_failed_lab_cannot_be_promoted_by_correction(education_engine):
    from app.models import ResultCorrection, CriterionAnswer
    with education_engine.begin() as c:
        lab_checklist(c)
        attempt(c, event_id=2, checklist_version_id=1, question_passed=False, passed=False, points=0, finalize=False)
        c.execute(CriterionAnswer.__table__.insert(), dict(attempt_id=1, criterion_id=1, satisfied=False))
        c.exec_driver_sql("UPDATE assessment_attempts SET finalized=TRUE WHERE id=1")
        with pytest.raises(DBAPIError, match="new attempt"):
            c.execute(ResultCorrection.__table__.insert(), dict(attempt_id=1, points=6, passed=True, reason="Override", source="teacher", operation_key="correction"))


def test_seminar_slots_are_distinct_and_cancelled_slot_can_be_replaced(education_engine):
    from datetime import time
    from app.models import Schedule, Lesson, EventCancellation
    with education_engine.begin() as c:
        c.execute(Schedule.__table__.insert(), dict(id=1, offering_id=1, day="Monday", time=time(10), type="Seminar", odd_or_even="even"))
        c.execute(Lesson.__table__.insert(), dict(id=1, schedule_id=1, date=date(2026, 2, 2)))
        def slot(key, category):
            c.execute(AssessmentEvent.__table__.insert(), dict(id=key, module_id=1, lesson_id=1, title="Test", category=category, max_points=10, required=True, attempt_policy="best"))
        slot(2, "seminar_start")
        slot(3, "seminar_end")
        with pytest.raises(DBAPIError, match="slot already"):
            slot(4, "seminar_start")
        c.execute(EventCancellation.__table__.insert(), dict(event_id=2, reason="Replaced"))
        slot(4, "seminar_start")
        assert list(c.scalars(select(AssessmentEvent.id).where(AssessmentEvent.lesson_id == 1).order_by(AssessmentEvent.id))) == [2, 3, 4]
