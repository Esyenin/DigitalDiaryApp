"""Teaching domain integration on isolated SQLite databases."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import (AssessmentAttempt, Attendance, AttendanceRevision, ChecklistCriterion,
                        ChecklistVersion, CriterionAnswer, Lesson, LessonDisposition,
                        Mark, Schedule, ScheduleGroupLink, TeachingAudit)
from app.ui.data import repository as repository_module


@pytest.fixture
def course(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'teaching.db'}")
    repo = repository_module.DiaryRepository()
    start = date.today() - timedelta(days=date.today().weekday())
    year = repo.academic_action("create_year", "Year", start, start + timedelta(weeks=52))
    term = repo.academic_action("create_term", year.id, "Term", start, 17)
    discipline = repo.academic_action("create_discipline", "Algorithms")
    groups = [repo.create_group(name, None) for name in ("A", "B")]
    students = [repo.create_student(group, "Ivan" if index == 0 else "Anna", "Student") for index, group in enumerate(groups)]
    offering = repo.academic_action("create_offering", term.id, discipline.id, "Shared", [g.id for g in groups])
    module = repo.academic_action("create_module", offering.id, "Module 1", 1, start, start + timedelta(weeks=8))
    yield repo, term, offering, module, students, groups
    repo.close()
    repo.engine.dispose()


def event(repo, module, category="checkpoint", **kwargs):
    return repo.teaching_action("create_event", module_id=module.id, title=category,
        category=category, max_points="12.50", required=True, attempt_policy="best", **kwargs)


def attempt(repo, assessment, student, score="8.25", **kwargs):
    return repo.teaching_action("record_attempt", event_id=assessment.id, student_id=student.id,
        points=score, work_completed=True, defended=False, passed=True, operation_key=uuid4().hex, **kwargs)


def lesson(repo, offering, groups, day=None):
    day = day or date.today()
    schedule = Schedule(offering_id=offering.id if offering else None, day=day.strftime("%A"), time=time(10),
                        odd_or_even="even", type="Seminar", is_assessment=True)
    repo.session.add(schedule)
    repo.session.flush()
    for group in groups:
        repo.session.add(ScheduleGroupLink(schedule_id=schedule.id, group_id=group.id))
    repo.session.flush()
    current = Lesson(schedule_id=schedule.id, date=day)
    repo.session.add(current)
    repo.session.commit()
    return current


def test_scores_are_decimal_idempotent_and_audited(course):
    repo, term, offering, module, students, groups = course
    assessment = event(repo, module)
    key = uuid4().hex
    payload = dict(event_id=assessment.id, student_id=students[0].id, points="8.25", work_completed=True,
                   defended=False, passed=True, operation_key=key)
    first = repo.teaching_action("record_attempt", **payload)
    assert repo.teaching_action("record_attempt", **payload).id == first.id
    assert len(list(repo.session.scalars(select(AssessmentAttempt)))) == 1
    with pytest.raises(repository_module.RepositoryError, match="reused"):
        repo.teaching_action("record_attempt", **{**payload, "points": "9.00"})
    correction_key = uuid4().hex
    correction = repo.teaching_action("correct_result", attempt_id=first.id, points="10.50", passed=True,
                                      reason="Rechecked solution", operation_key=correction_key)
    assert repo.teaching_action("correct_result", attempt_id=first.id, points="10.50", passed=True,
                               reason="Rechecked solution", operation_key=correction_key).id == correction.id
    totals = repo.teaching_summary(offering.id, students[0].id)
    assert totals["earned"] == Decimal("10.50")
    assert totals["maximum"] == Decimal("12.50")
    assert totals["remaining"] == Decimal("2.00")
    assert not totals["debts"]
    assert repo.session.get(AssessmentAttempt, first.id).points == Decimal("8.25")
    assert len(list(repo.session.scalars(select(TeachingAudit)))) == 3


def test_two_tests_on_one_seminar_have_independent_results(course):
    repo, term, offering, module, students, groups = course
    current = lesson(repo, offering, groups)
    start = event(repo, module, "seminar_start", lesson_id=current.id)
    end = event(repo, module, "seminar_end", lesson_id=current.id)
    attempt(repo, start, students[0], "7.50")
    attempt(repo, end, students[0], "11.25")
    assert repo.teaching_summary(offering.id, students[0].id)["earned"] == Decimal("18.75")
    assert not list(repo.session.scalars(select(Mark)))
    with pytest.raises(repository_module.RepositoryError, match="slot"):
        event(repo, module, "seminar_start", lesson_id=current.id)


def test_latest_attempt_limit_debts_and_cancellation(course):
    repo, term, offering, module, students, groups = course
    assessment = repo.teaching_action("create_event", module_id=module.id, title="Latest", category="additional",
        max_points="20", required=True, attempt_policy="latest", max_attempts=2)
    attempt(repo, assessment, students[0], "15")
    repo.teaching_action("record_attempt", event_id=assessment.id, student_id=students[0].id,
        points=0, passed=False, work_completed=True, defended=False, operation_key=uuid4().hex)
    totals = repo.teaching_summary(offering.id, students[0].id)
    assert totals["earned"] == 0 and totals["remaining"] == 0
    assert totals["debts"] == [dict(id=assessment.id, title="Latest")]
    with pytest.raises(repository_module.RepositoryError, match="limit"):
        attempt(repo, assessment, students[0])
    with pytest.raises(repository_module.RepositoryError, match="results"):
        repo.teaching_action("cancel_event", event_id=assessment.id, reason="Cancel")


def test_lab_versions_and_resit_through_consultation(course):
    repo, term, offering, module, students, groups = course
    assessment = event(repo, module, "lab")
    lab = repo.teaching_action("create_lab", event_id=assessment.id, title="Lab 1")
    first = repo.teaching_action("create_checklist", lab_id=lab.id, criteria=["Runs", "Tests"])
    criteria = list(repo.session.scalars(select(ChecklistCriterion).where(ChecklistCriterion.version_id == first.id)))
    failure = repo.teaching_action("record_attempt", event_id=assessment.id, student_id=students[0].id, points=0,
        work_completed=True, defended=True, passed=False, operation_key=uuid4().hex, checklist_version_id=first.id,
        answers={item.id: False for item in criteria}, question_passed=False, additional_answer="No answer")
    second = repo.teaching_action("create_checklist", lab_id=lab.id, criteria=["Runs", "Tests", "Explains"])
    assert second.revision == 2
    consultation = repo.teaching_action("create_consultation", starts_at=datetime.now(timezone.utc))
    visit = repo.teaching_action("register_visit", consultation_id=consultation.id, student_id=students[0].id,
                                purpose="Lab resit", question="Explain recursion")
    latest = list(repo.session.scalars(select(ChecklistCriterion).where(ChecklistCriterion.version_id == second.id)))
    success = repo.teaching_action("record_attempt", event_id=assessment.id, student_id=students[0].id, points="12.50",
        work_completed=True, defended=True, passed=True, operation_key=uuid4().hex, checklist_version_id=second.id,
        answers={item.id: True for item in latest}, question_passed=True, additional_answer="Explained recursion",
        consultation_visit_id=visit.id)
    assert success.attempt_number == 2 and success.consultation_visit_id == visit.id
    assert repo.session.get(AssessmentAttempt, failure.id).checklist_version_id == first.id
    assert len(list(repo.session.scalars(select(CriterionAnswer).where(CriterionAnswer.attempt_id == failure.id)))) == 2
    assert repo.teaching_summary(offering.id, students[0].id)["earned"] == Decimal("12.50")
    assert not list(repo.session.scalars(select(Attendance)))


def test_lateness_of_fixed_absent_participant_and_reasoned_correction(course, monkeypatch):
    repo, term, offering, module, students, groups = course
    current = lesson(repo, offering, groups)
    completed = datetime.now(timezone.utc) - timedelta(minutes=7)
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return completed if tz else completed.replace(tzinfo=None)
    monkeypatch.setattr(repository_module, "datetime", FixedDateTime)
    repo.complete_lesson_roster(current)
    participant_ids = [item.id for item in current.participants]
    revision = repo.teaching_action("record_attendance", lesson_id=current.id, student_id=students[0].id,
        status="present", reason="Arrived after roll call", arrived_at=completed + timedelta(minutes=7),
        operation_key=uuid4().hex)
    assert revision.status == "late" and revision.late_seconds == 420
    assert repo.session.get(Attendance, revision.attendance_id).is_visited
    corrected = repo.teaching_action("record_attendance", lesson_id=current.id, student_id=students[0].id,
        status="excused", reason="Medical confirmation", source="teacher", operation_key=uuid4().hex)
    assert corrected.status == "excused"
    assert len(list(repo.session.scalars(select(AttendanceRevision)))) == 2
    assert [item.id for item in current.participants] == participant_ids


def test_holiday_generation_and_move_do_not_delete_original(course):
    repo, term, offering, module, students, groups = course
    future_day = date.today() + timedelta(days=2)
    current = lesson(repo, offering, groups, future_day)
    holiday = repo.teaching_action("add_non_teaching_day", term_id=term.id, day=future_day, reason="Holiday")
    assert repo.teaching_action("add_non_teaching_day", term_id=term.id, day=future_day, reason="Holiday").id == holiday.id
    assert repo.session.get(Lesson, current.id) is not None
    change = repo.teaching_action("set_lesson_disposition", lesson_id=current.id, status="moved",
                                  reason="Make-up", new_date=future_day + timedelta(days=1))
    assert repo.teaching_action("set_lesson_disposition", lesson_id=current.id, status="moved",
        reason="Make-up", new_date=future_day + timedelta(days=1)).id == change.id
    assert change.replacement_lesson_id != current.id
    assert repo.session.get(Lesson, current.id).date == future_day


def test_plan_comments_keep_history(course):
    repo, term, offering, module, students, groups = course
    plan = repo.teaching_action("create_plan", student_id=students[0].id, title="Project", kind="project", offering_id=offering.id)
    stage = repo.teaching_action("add_plan_stage", plan_id=plan.id, title="Design", position=1)
    first = repo.teaching_action("record_plan_entry", stage_id=stage.id, completed=False, comment="Draft reviewed")
    second = repo.teaching_action("record_plan_entry", stage_id=stage.id, completed=True, comment="Design accepted")
    assert first.id != second.id and not first.completed and second.completed


def test_failed_attempt_rolls_back_without_losing_old_results(course):
    repo, term, offering, module, students, groups = course
    assessment = event(repo, module)
    old = attempt(repo, assessment, students[0])
    with pytest.raises(repository_module.RepositoryError, match="maximum"):
        attempt(repo, assessment, students[0], "99")
    assert list(repo.session.scalars(select(AssessmentAttempt.id))) == [old.id]
    repo.archive_student(students[0], reason="Graduated")
    assert repo.teaching_summary(offering.id, students[0].id)["earned"] == Decimal("8.25")


def test_cancelled_seminar_slot_can_be_replaced_without_results(course):
    repo, term, offering, module, students, groups = course
    current = lesson(repo, offering, groups)
    original = event(repo, module, "seminar_start", lesson_id=current.id)
    repo.teaching_action("cancel_event", event_id=original.id, reason="Revised test cost before use")
    replacement = event(repo, module, "seminar_start", lesson_id=current.id)
    assert replacement.id != original.id
    assert len(repo.teaching_summary(offering.id, students[0].id)["events"]) == 1


def test_version_switch_conflicts_include_future_assessments(course):
    repo, term, offering, module, students, groups = course
    current = lesson(repo, offering, groups, date.today() + timedelta(days=2))
    event(repo, module, "seminar_start", lesson_id=current.id)
    with pytest.raises(repository_module.RepositoryError, match=current.date.isoformat()):
        repo._reject_conflicting_future_lessons(current.schedule, date.today() + timedelta(days=1))


def test_old_versioned_workbook_without_new_context_columns_restores(tmp_path, monkeypatch):
    from openpyxl import load_workbook
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'legacy_export.db'}")
    source = repository_module.DiaryRepository()
    try:
        group = source.create_group("Legacy", None)
        source.create_student(group, "Name", "Surname")
        current = lesson(source, None, [group])
        path = source.export_to_xlsx(tmp_path / "old.xlsx")
        workbook = load_workbook(path)
        for sheet, omitted in (("schedules", {"offering_id"}), ("lessons", {"roster_time_basis", "roster_completed_at"})):
            worksheet = workbook[sheet]
            for index in reversed(range(1, worksheet.max_column + 1)):
                if worksheet.cell(1, index).value in omitted:
                    worksheet.delete_cols(index)
        workbook.save(path)
        workbook.close()
        monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'legacy_restore.db'}")
        target = repository_module.DiaryRepository()
        try:
            preview = target.preview_import_from_xlsx(path, strategy="standard")
            assert not preview.errors
            target.import_from_preview(preview)
            restored = target.session.scalar(select(Lesson))
            assert restored.id == current.id and restored.roster_time_basis == "unknown"
            assert restored.roster_completed_at is None
        finally:
            target.close()
            target.engine.dispose()
    finally:
        source.close()
        source.engine.dispose()


def test_concurrent_attempts_do_not_double_count_or_reuse_numbers(course, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    repo, term, offering, module, students, groups = course
    assessment = event(repo, module)
    database_url = repo.engine.url.render_as_string(hide_password=False)
    monkeypatch.setattr(repository_module, "DATABASE_URL", database_url)
    event_id, student_id = assessment.id, students[0].id

    def write(key):
        other = repository_module.DiaryRepository()
        try:
            result = other.teaching_action("record_attempt", event_id=event_id, student_id=student_id,
                points="10.00", passed=True, work_completed=True, defended=False, operation_key=key)
            return result.id, result.attempt_number
        finally:
            other.close()
            other.engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(write, ["same-operation", "same-operation"]))
    assert results[0] == results[1]
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(write, ["second-operation", "third-operation"]))
    assert {number for key, number in results} == {2, 3}
    repo.refresh()
    assert repo.teaching_summary(offering.id, student_id)["earned"] == Decimal("10.00")
    assert len(list(repo.session.scalars(select(AssessmentAttempt)))) == 3


def test_failure_after_finalization_rolls_back_entire_attempt(course, monkeypatch):
    from app.services.teaching import TeachingService
    repo, term, offering, module, students, groups = course
    assessment = event(repo, module)
    prior = attempt(repo, assessment, students[0])

    def fail_audit(*args, **kwargs):
        raise SQLAlchemyError("Injected audit failure after finalization")

    monkeypatch.setattr(TeachingService, "_audit", fail_audit)
    with pytest.raises(repository_module.RepositoryError, match="Injected"):
        attempt(repo, assessment, students[0], "11.00")
    assert list(repo.session.scalars(select(AssessmentAttempt.id))) == [prior.id]
    assert repo.teaching_summary(offering.id, students[0].id)["earned"] == Decimal("8.25")


def test_attendance_correction_does_not_invent_a_new_arrival(course):
    repo, term, offering, module, students, groups = course
    current = lesson(repo, offering, groups)
    repo.complete_lesson_roster(current)
    revision = repo.teaching_action("record_attendance", lesson_id=current.id, student_id=students[0].id,
        status="present", reason="Teacher corrected mistaken absence", mode="correction", operation_key=uuid4().hex)
    assert revision.status == "present" and revision.arrived_at is None and revision.late_seconds is None
    assert repo.session.get(Attendance, revision.attendance_id).is_visited


def test_second_move_targets_replacement_and_actual_date_ignores_template_parity(course):
    repo, term, offering, module, students, groups = course
    day = date.today() + timedelta(days=2)
    current = lesson(repo, offering, groups, day)
    moved = repo.teaching_action("set_lesson_disposition", lesson_id=current.id, status="moved", reason="First move",
                                new_date=day + timedelta(weeks=1))
    with pytest.raises(repository_module.RepositoryError, match="already moved"):
        repo.teaching_action("set_lesson_disposition", lesson_id=current.id, status="moved", reason="Wrong source",
                             new_date=day + timedelta(weeks=2))
    replacement = repo.session.get(Lesson, moved.replacement_lesson_id)
    monday = replacement.date - timedelta(days=replacement.date.weekday())
    assert replacement.id in {item.id for item in repo.lessons_for_week(monday, "odd")}
