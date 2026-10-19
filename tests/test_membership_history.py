"""Regression coverage for dated membership and fixed lesson rosters."""

from copy import deepcopy
from datetime import date, time, timedelta

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError

from app.models import (Attendance, Comment, Group, GroupMembership, Lesson,
                        LessonParticipant, Mark, Schedule, ScheduleGroupLink, Student)
from app.services.ormservice import OrmService, OrmServiceError
from app.ui.data import repository as repository_module


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'membership.db'}")
    repository = repository_module.DiaryRepository()
    yield repository
    repository.close()
    repository.engine.dispose()


def _lesson(repo, groups):
    schedule = Schedule(
        day=date.today().strftime("%A"), time=time(10), odd_or_even="even",
        type="Seminar", is_assessment=True, effective_from=date.today(),
    )
    repo.session.add(schedule)
    repo.session.flush()
    repo.session.add_all(
        ScheduleGroupLink(schedule_id=schedule.id, group_id=group.id) for group in groups
    )
    repo.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=date.today(), topic="History")
    repo.session.add(lesson)
    repo.session.commit()
    return lesson


def test_transfer_preserves_fixed_multigroup_roster_and_results(repo):
    first = repo.create_group("First", None)
    second = repo.create_group("Second", None)
    third = repo.create_group("Third", None)
    student = repo.create_student(first, "Ivan", "Ivanov")
    other = repo.create_student(second, "Anna", "Petrova")
    lesson = _lesson(repo, [first, second])

    assert {item.id for item in repo.students_for_lesson(lesson)} == {student.id, other.id}
    assert lesson.participants_complete
    participant = next(item for item in lesson.participants if item.student_id == student.id)
    assert participant.group_id == first.id
    repo.save_lesson_student_record(
        lesson, student, attended=True, comment_text="Good", mark_value=91,
    )
    result_ids = (
        repo.session.scalar(select(Attendance.id).where(Attendance.student_id == student.id)),
        repo.session.scalar(select(Mark.id).where(Mark.student_id == student.id)),
        repo.session.scalar(select(Comment.id).where(Comment.student_id == student.id)),
    )
    repo.transfer_student(student, third, date.today())
    repo.session.expire_all()
    assert student.group_id == third.id
    assert {item.id for item in repo.students_for_lesson(lesson)} == {student.id, other.id}
    assert repo._group_participant_ids(lesson, first.id) == {student.id}
    assert repo._group_participant_ids(lesson, second.id) == {other.id}
    assert repo.group_stats(first)["attendance"] == 100
    assert repo.student_stats(student)["overall"] == 91
    assert [repo.session.get(model, key).id for model, key in zip(
        (Attendance, Mark, Comment), result_ids
    )] == list(result_ids)


def test_archive_hides_student_and_preserves_lesson(repo):
    group = repo.create_group("Archive", None)
    student = repo.create_student(group, "Ivan", "Ivanov")
    lesson = _lesson(repo, [group])
    repo.students_for_lesson(lesson)
    repo.save_lesson_student_record(lesson, student, attended=True, comment_text="", mark_value=83)
    repo.archive_student(student, reason="Graduated")

    assert student.id not in {item.id for item in repo.list_students()}
    assert student.id in {item.id for item in repo.list_students(include_archived=True)}
    assert student.id in {item.id for item in repo.students_for_lesson(lesson)}
    assert repo.student_stats(student)["attendance"] == 100
    assert repo.membership_history(student)[-1].end_date == date.today()
    assert repo.session.scalar(select(Mark.data).where(Mark.student_id == student.id)) == 83


def test_future_lesson_roster_stays_provisional(repo):
    first = repo.create_group("First", None)
    second = repo.create_group("Second", None)
    student = repo.create_student(first, "Ivan", "Ivanov")
    schedule = Schedule(
        day="Monday", time=time(10), odd_or_even="even", type="Seminar",
        effective_from=date.today(),
    )
    repo.session.add(schedule)
    repo.session.flush()
    repo.session.add(ScheduleGroupLink(schedule_id=schedule.id, group_id=first.id))
    repo.session.flush()
    future = Lesson(schedule_id=schedule.id, date=date.today() + timedelta(days=7))
    repo.session.add(future)
    repo.session.commit()
    assert {item.id for item in repo.students_for_lesson(future)} == {student.id}
    assert not future.participants_complete
    assert not future.participants
    repo.transfer_student(student, second, date.today())
    assert repo.students_for_lesson(future) == []
    assert not future.participants


def test_group_archive_requires_no_active_use(repo):
    group = repo.create_group("Archive", None)
    student = repo.create_student(group, "Ivan", "Ivanov")
    with pytest.raises(repository_module.RepositoryError, match="still used"):
        repo.archive_group(group)
    repo.archive_student(student, reason="Graduated")
    repo.archive_group(group)
    assert group.id not in {item.id for item in repo.list_groups()}
    assert group.id in {item.id for item in repo.list_groups(include_archived=True)}


def test_database_guards_prevent_bypass_and_overlap(repo):
    first = repo.create_group("First", None)
    second = repo.create_group("Second", None)
    student = repo.create_student(first, "Ivan", "Ivanov")
    with pytest.raises(IntegrityError, match="transfer requires"):
        repo.session.execute(update(Student).where(Student.id == student.id).values(group_id=second.id))
    repo.session.rollback()
    with pytest.raises(IntegrityError, match="overlapping"):
        repo.session.add(GroupMembership(
            student_id=student.id, group_id=second.id,
            start_date=date.today(), known_from=date.today(), origin="recorded",
        ))
        repo.session.flush()
    repo.session.rollback()
    with pytest.raises(IntegrityError, match="create an active student"):
        repo.session.add(Student(
            group_id=second.id, surname="Invalid", first_name="Archived",
            status="archived", archived_at=date.today(), archive_reason="Test",
        ))
        repo.session.flush()
    repo.session.rollback()
    with pytest.raises(IntegrityError, match="archive requires closing"):
        repo.session.execute(update(Student).where(Student.id == student.id).values(
            status="archived", archived_at=date.today(), archive_reason="Test",
        ))
    repo.session.rollback()
    assert OrmService(repo.session, auto_commit=False).delete(student) is None
    with pytest.raises(IntegrityError, match="archive groups"):
        repo.session.execute(delete(Group).where(Group.id == first.id))
    repo.session.rollback()
    assert repo.session.get(Student, student.id).group_id == first.id


def test_fixed_roster_is_immutable_through_direct_sql(repo):
    group = repo.create_group("Fixed", None)
    other_group = repo.create_group("Other", None)
    student = repo.create_student(group, "Ivan", "Ivanov")
    outsider = repo.create_student(other_group, "Anna", "Petrova")
    lesson = _lesson(repo, [group])
    repo.students_for_lesson(lesson)
    participant_id = lesson.participants[0].id
    with pytest.raises(IntegrityError, match="immutable"):
        repo.session.execute(delete(LessonParticipant).where(LessonParticipant.id == participant_id))
    repo.session.rollback()
    with pytest.raises(IntegrityError, match="immutable"):
        repo.session.execute(update(Lesson).where(Lesson.id == lesson.id).values(participants_complete=False))
    repo.session.rollback()
    with pytest.raises(IntegrityError, match="outside fixed lesson roster"):
        repo.session.add(Attendance(student_id=outsider.id, lesson_id=lesson.id, is_visited=True))
        repo.session.flush()
    repo.session.rollback()
    with pytest.raises(IntegrityError, match="immutable"):
        repo.session.add(LessonParticipant(
            student_id=outsider.id, lesson_id=lesson.id, source="evidence"
        ))
        repo.session.flush()
    repo.session.rollback()
    with pytest.raises(IntegrityError, match="lesson history"):
        repo.session.execute(delete(Lesson).where(Lesson.id == lesson.id))
    repo.session.rollback()
    assert repo.session.get(LessonParticipant, participant_id).student_id == student.id


@pytest.mark.parametrize("archived", [False, True])
def test_full_xlsx_restore_preserves_membership_and_roster(repo, tmp_path, monkeypatch, archived):
    first = repo.create_group("First", None)
    second = repo.create_group("Second", None)
    student = repo.create_student(first, "Ivan", "Ivanov")
    lesson = _lesson(repo, [first])
    repo.students_for_lesson(lesson)
    repo.save_lesson_student_record(lesson, student, attended=True, comment_text="Saved", mark_value=90)
    repo.transfer_student(student, second, date.today())
    if archived:
        repo.archive_student(student, reason="Graduated")
    source_ids = (student.id, lesson.id)
    workbook = repo.export_to_xlsx(tmp_path / "history.xlsx")

    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'restored.db'}")
    restored = repository_module.DiaryRepository()
    try:
        preview = restored.preview_import_from_xlsx(workbook, strategy="standard")
        assert not preview.errors
        assert len(preview.data["group_memberships"]) == 2
        assert len(preview.data["lesson_participants"]) == 1
        restored.import_from_preview(preview)
        restored_student = restored.session.scalar(select(Student))
        restored_lesson = restored.session.scalar(select(Lesson))
        assert (restored_student.id, restored_lesson.id) == source_ids
        assert len(restored.membership_history(restored_student)) == 2
        assert restored_student.status == ("archived" if archived else "active")
        assert restored.students_for_lesson(restored_lesson)[0].id == restored_student.id
        assert restored.session.scalar(select(Mark.data)) == 90
        with pytest.raises(repository_module.RepositoryError, match="empty database"):
            restored.import_from_preview(preview)
    finally:
        restored.close()
        restored.engine.dispose()


def test_failed_xlsx_restore_rolls_back_and_keeps_guards(repo, tmp_path, monkeypatch):
    group = repo.create_group("First", None)
    repo.create_student(group, "Ivan", "Ivanov")
    workbook = repo.export_to_xlsx(tmp_path / "history.xlsx")
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'restore_fail.db'}")
    restored = repository_module.DiaryRepository()
    try:
        good = restored.preview_import_from_xlsx(workbook, strategy="standard")
        bad = deepcopy(good)
        conflicting = dict(bad.data["group_memberships"][0])
        conflicting["id"] = 999
        bad.data["group_memberships"].append(conflicting)
        with pytest.raises(repository_module.RepositoryError, match="overlapping"):
            restored.import_from_preview(bad)
        assert restored.session.scalar(select(Student.id)) is None
        assert restored.session.scalar(text(
            "SELECT count(*) FROM sqlite_master WHERE type='trigger' "
            "AND name='student_membership_insert'"
        )) == 1
        restored.import_from_preview(good)
        assert restored.session.scalar(select(GroupMembership.id)) is not None
    finally:
        restored.close()
        restored.engine.dispose()


def test_generic_xlsx_facade_cannot_silently_drop_history(repo, tmp_path):
    group = repo.create_group("First", None)
    repo.create_student(group, "Ivan", "Ivanov")
    service = OrmService(repo.session, auto_commit=False)
    with pytest.raises(OrmServiceError, match="Full history export"):
        service.export_to_xlsx(None, tmp_path / "incomplete.xlsx")
    workbook = repo.export_to_xlsx(tmp_path / "complete.xlsx")
    with pytest.raises(OrmServiceError, match="History workbook"):
        service.import_from_xlsx(workbook)


def test_concurrent_transfer_uses_latest_membership(repo, tmp_path, monkeypatch):
    first = repo.create_group("First", None)
    second = repo.create_group("Second", None)
    third = repo.create_group("Third", None)
    student = repo.create_student(first, "Ivan", "Ivanov")
    second_repository = repository_module.DiaryRepository()
    try:
        stale_student = second_repository.get_student(student.id)
        repo.transfer_student(student, second, date.today())
        second_repository.transfer_student(
            stale_student, second_repository.get_group(third.id), date.today()
        )
        repo.session.expire_all()
        assert student.group_id == third.id
        history = repo.membership_history(student)
        assert [item.group_id for item in history] == [first.id, second.id, third.id]
        assert [item.end_date for item in history] == [date.today(), date.today(), None]
    finally:
        second_repository.close()
        second_repository.engine.dispose()


@pytest.mark.parametrize("strategy", ["standard", "smart"])
def test_excel_group_change_without_date_is_rejected(repo, tmp_path, strategy):
    first = repo.create_group("First", None)
    second = repo.create_group("Second", None)
    student = repo.create_student(first, "Ivan", "Ivanov")
    preview = repository_module.ImportPreview(
        source_path=tmp_path / "student.xlsx", strategy=strategy, mode="merge",
        data={"students": [{
            "id": student.id, "group_id": second.id,
            "first_name": student.first_name, "surname": student.surname,
        }]},
    )
    with pytest.raises(repository_module.RepositoryError, match="transfer date"):
        repo.import_from_preview(preview)
    assert repo.session.scalar(select(Student.group_id).where(Student.id == student.id)) == first.id
    assert repo.session.scalar(select(GroupMembership.group_id).where(
        GroupMembership.student_id == student.id
    )) == first.id
