from datetime import date, time

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import Attendance, Comment, Group, Lesson, Mark, Schedule, ScheduleGroupLink, Student
from app.services.ormservice import OrmService
from app.services.schedule import ScheduleService
from app.services.schedule_group_links import ScheduleGroupLinkService
from app.ui.data import repository as repository_module
from app.ui.data.calendar import SemesterSettings


TODAY = date(2026, 2, 10)
SWITCH = date(2026, 2, 11)
SETTINGS = SemesterSettings(start_date=date(2026, 2, 2), total_weeks=4)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'history.db'}")
    repository = repository_module.DiaryRepository()
    yield repository
    repository.close()
    repository.engine.dispose()


def _schedule(repo, *, future_topic=None, future_result=None):
    group = Group(name="IU7-11")
    other_group = Group(name="IU7-12")
    schedule = Schedule(
        day="Monday", time=time(10), odd_or_even="even",
        type="Seminar", is_assessment=True,
    )
    repo.session.add_all([group, other_group, schedule])
    repo.session.flush()
    link = ScheduleGroupLink(group_id=group.id, schedule_id=schedule.id)
    student = Student(group_id=group.id, surname="Ivanov", first_name="Ivan")
    repo.session.add_all([link, student])
    repo.session.flush()
    past = Lesson(schedule_id=schedule.id, date=date(2026, 2, 9), topic="Past lesson")
    future = Lesson(schedule_id=schedule.id, date=date(2026, 2, 16), topic=future_topic)
    repo.session.add_all([past, future])
    repo.session.flush()
    repo.session.add_all([
        Attendance(student_id=student.id, lesson_id=past.id, is_visited=True),
        Mark(student_id=student.id, lesson_id=past.id, data=87),
        Comment(student_id=student.id, lesson_id=past.id, data="Passed"),
    ])
    if future_result == "attendance":
        repo.session.add(Attendance(student_id=student.id, lesson_id=future.id, is_visited=True))
    elif future_result == "mark":
        repo.session.add(Mark(student_id=student.id, lesson_id=future.id, data=90))
    elif future_result == "comment":
        repo.session.add(Comment(student_id=student.id, lesson_id=future.id, data="Planned"))
    repo.session.commit()
    return schedule, group, other_group, link, student, past, future


def _update(repo, schedule, groups, **changes):
    values = {
        "day": "Monday", "lesson_time": time(10), "week_type": "even",
        "lesson_type": "Seminar", "is_assessment": True,
    }
    values.update(changes)
    return repo.update_schedule(
        schedule, None, groups, settings=SETTINGS, as_of=TODAY,
        effective_from=SWITCH, **values,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"day": "Tuesday"}, {"week_type": "odd"},
        {"lesson_time": time(12)}, {"lesson_type": "Lab Work"},
        {"is_assessment": False}, {"groups": "other"},
    ],
)
def test_version_change_preserves_historical_ids_and_values(repo, change):
    schedule, group, other, link, student, past, future = _schedule(repo)
    ids = {
        "lesson": past.id, "link": link.id,
        "attendance": repo.session.scalar(select(Attendance.id)),
        "mark": repo.session.scalar(select(Mark.id)),
        "comment": repo.session.scalar(select(Comment.id)),
    }
    groups = [other] if change.pop("groups", None) else [group]
    next_version = _update(repo, schedule, groups, **change)

    repo.session.expire_all()
    assert next_version.id != schedule.id
    assert next_version.series_key == schedule.series_key
    assert (schedule.revision, next_version.revision) == (1, 2)
    assert schedule.effective_until == SWITCH
    assert next_version.effective_from == SWITCH
    assert (schedule.day, schedule.time, schedule.type) == ("Monday", time(10), "Seminar")
    assert repo.session.get(ScheduleGroupLink, ids["link"]).group_id == group.id
    assert repo.session.get(Lesson, ids["lesson"]).topic == "Past lesson"
    assert repo.session.scalar(
        select(Lesson.id).where(
            Lesson.schedule_id == schedule.id, Lesson.date == future.date
        )
    ) is None
    assert repo.session.get(Attendance, ids["attendance"]).is_visited is True
    assert repo.session.get(Mark, ids["mark"]).data == 87
    assert repo.session.get(Comment, ids["comment"]).data == "Passed"
    assert {item.group_id for item in next_version.group_links} == {item.id for item in groups}
    assert past.id in {lesson.id for lesson in repo.lessons_for_week(date(2026, 2, 9), "even")}
    assert repo.student_stats(student)["overall"] > 0


@pytest.mark.parametrize("future_result", ["attendance", "mark", "comment", "topic"])
def test_filled_future_lesson_blocks_switch_and_deactivation(repo, future_result):
    schedule, group, _, link, _, past, future = _schedule(
        repo,
        future_topic="Planned" if future_result == "topic" else None,
        future_result=None if future_result == "topic" else future_result,
    )
    with pytest.raises(repository_module.RepositoryError, match="2026-02-16"):
        _update(repo, schedule, [group], day="Tuesday")
    with pytest.raises(repository_module.RepositoryError, match="2026-02-16"):
        repo.delete_schedule(schedule, as_of=TODAY, effective_from=SWITCH)
    repo.session.expire_all()
    assert schedule.effective_until is None
    assert repo.session.get(Lesson, past.id) is not None
    assert repo.session.get(Lesson, future.id) is not None
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.scalar(select(Schedule).where(Schedule.series_key == schedule.series_key).order_by(Schedule.revision.desc())).id == schedule.id


def test_all_conflicting_dates_are_reported(repo):
    schedule, group, _, _, _, _, _ = _schedule(repo, future_topic="First")
    repo.session.add(Lesson(schedule_id=schedule.id, date=date(2026, 2, 23), topic="Second"))
    repo.session.commit()
    with pytest.raises(repository_module.RepositoryError) as error:
        _update(repo, schedule, [group], day="Tuesday")
    assert "2026-02-16" in str(error.value)
    assert "2026-02-23" in str(error.value)


def test_deactivation_keeps_history_and_stops_generation(repo):
    schedule, group, _, link, student, past, future = _schedule(repo)
    repo.delete_schedule(schedule, as_of=TODAY, effective_from=SWITCH)
    repo.ensure_lessons_for_semester(SETTINGS)
    assert schedule.effective_until == SWITCH
    assert repo.session.get(Schedule, schedule.id) is not None
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.get(Lesson, past.id) is not None
    assert repo.session.get(Lesson, future.id) is None
    assert all(lesson.date < SWITCH for lesson in schedule.lessons)
    assert repo.group_stats(group)["overall"] == 87
    assert repo.student_stats(student)["overall"] == 87


def test_future_date_is_required_for_changes(repo):
    schedule, group, _, _, _, _, _ = _schedule(repo)
    for target in (None, TODAY):
        with pytest.raises(repository_module.RepositoryError, match="future effective date"):
            repo.update_schedule(
                schedule, None, [group], "Tuesday", time(10), "even", "Seminar",
                True, SETTINGS, as_of=TODAY, effective_from=target,
            )
    assert schedule.effective_until is None


def test_unchanged_save_keeps_version_and_link_ids(repo):
    schedule, group, _, link, _, past, _ = _schedule(repo)
    result = _update(repo, schedule, [group])
    assert result.id == schedule.id
    assert schedule.effective_until is None
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.get(Lesson, past.id) is not None


def test_empty_unused_schedule_can_be_deleted(repo):
    schedule = Schedule(day="Monday", time=time(10), odd_or_even="even", type="Seminar")
    repo.session.add(schedule)
    repo.session.commit()
    repo.delete_schedule(schedule, as_of=TODAY)
    assert repo.session.get(Schedule, schedule.id) is None


def test_period_overlap_is_rejected_by_database(repo):
    schedule = Schedule(day="Monday", time=time(10), odd_or_even="even", type="Seminar")
    repo.session.add(schedule)
    repo.session.commit()
    overlapping = Schedule(
        series_key=schedule.series_key, revision=2,
        effective_from=date(2026, 2, 12), day="Tuesday", time=time(11),
        odd_or_even="even", type="Seminar",
    )
    repo.session.add(overlapping)
    with pytest.raises(IntegrityError, match="overlapping schedule periods"):
        repo.session.flush()
    repo.session.rollback()
    assert repo.session.get(Schedule, schedule.id) is not None


def test_failed_switch_rolls_back_every_change(repo, monkeypatch):
    schedule, group, _, link, _, past, future = _schedule(repo)
    ids = {
        "attendance": repo.session.scalar(select(Attendance.id)),
        "mark": repo.session.scalar(select(Mark.id)),
        "comment": repo.session.scalar(select(Comment.id)),
    }

    def fail_generation(*_args):
        raise SQLAlchemyError("simulated generation failure")

    monkeypatch.setattr(repo, "ensure_lessons_for_schedule", fail_generation)
    with pytest.raises(repository_module.RepositoryError, match="not updated"):
        _update(repo, schedule, [group], day="Tuesday")

    repo.session.expire_all()
    assert schedule.effective_until is None
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.get(Lesson, past.id) is not None
    assert repo.session.get(Lesson, future.id) is not None
    assert repo.session.get(Attendance, ids["attendance"]) is not None
    assert repo.session.get(Mark, ids["mark"]) is not None
    assert repo.session.get(Comment, ids["comment"]) is not None
    assert len(repo.session.scalars(select(Schedule)).all()) == 1


def test_repeated_generation_keeps_lesson_ids(repo):
    schedule, group, _, _, _, past, _ = _schedule(repo)
    next_version = _update(repo, schedule, [group], day="Tuesday")
    repo.ensure_lessons_for_semester(SETTINGS)
    ids_before = {
        (lesson.schedule_id, lesson.date): lesson.id
        for lesson in repo.session.scalars(select(Lesson))
    }
    repo.ensure_lessons_for_semester(SETTINGS)
    ids_after = {
        (lesson.schedule_id, lesson.date): lesson.id
        for lesson in repo.session.scalars(select(Lesson))
    }
    assert ids_after == ids_before
    assert (schedule.id, past.date) in ids_after
    assert any(key[0] == next_version.id for key in ids_after)


def test_group_stats_keep_old_version_after_group_change(repo):
    schedule, old_group, new_group, _, student, past, _ = _schedule(repo)
    next_version = _update(repo, schedule, [new_group], day="Tuesday")
    assert {link.group_id for link in schedule.group_links} == {old_group.id}
    assert {link.group_id for link in next_version.group_links} == {new_group.id}
    assert repo.group_stats(old_group)["overall"] == 87
    assert repo.student_stats(student)["overall"] == 87
    assert past.id in {lesson.id for lesson in repo.lessons_for_week(past.date, "even")}


def test_closed_version_cannot_be_edited_or_deleted(repo):
    schedule, group, _, link, _, past, _ = _schedule(repo)
    _update(repo, schedule, [group], day="Tuesday")
    with pytest.raises(repository_module.RepositoryError, match="latest schedule version"):
        _update(repo, schedule, [group], lesson_time=time(12))
    with pytest.raises(repository_module.RepositoryError, match="already closed"):
        repo.delete_schedule(schedule, as_of=TODAY, effective_from=date(2026, 2, 18))
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.get(Lesson, past.id).topic == "Past lesson"


def test_generic_orm_facade_cannot_mutate_used_schedule_or_group_links(repo):
    schedule, group, other, link, _, past, _ = _schedule(repo)
    service = OrmService(repo.session, auto_commit=False)
    assert service.update(schedule, {"day": "Tuesday"}) is None
    assert service.update(link, {"group_id": other.id}) is None
    assert service.delete(schedule) is None
    assert service.delete(ScheduleGroupLink(id=link.id)) is None
    repo.session.expire_all()
    assert schedule.day == "Monday"
    assert repo.session.get(ScheduleGroupLink, link.id).group_id == group.id
    assert repo.session.get(Lesson, past.id) is not None


def test_direct_services_and_sql_cannot_rewrite_historical_version(repo):
    schedule, group, other, link, _, past, _ = _schedule(repo)
    assert ScheduleService().apply_update(schedule, {"day": "Tuesday"}) is None
    assert ScheduleGroupLinkService().apply_update(link, {"group_id": other.id}) is None
    for statement in (
        "UPDATE schedules SET day = 'Tuesday' WHERE id = :id",
        "DELETE FROM schedules WHERE id = :id",
        "DELETE FROM schedulegrouplinks WHERE schedule_id = :id",
        "INSERT INTO schedulegrouplinks (group_id, schedule_id) VALUES (:other, :id)",
    ):
        with pytest.raises(IntegrityError):
            repo.session.execute(text(statement), {"id": schedule.id, "other": other.id})
        repo.session.rollback()
    assert repo.session.get(Schedule, schedule.id).day == "Monday"
    assert repo.session.get(ScheduleGroupLink, link.id).group_id == group.id
    assert repo.session.get(Lesson, past.id).topic == "Past lesson"


def test_link_cannot_move_from_unused_schedule_into_historical_version(repo):
    historical, group, other, historical_link, _, past, _ = _schedule(repo)
    source = Schedule(day="Tuesday", time=time(11), odd_or_even="even", type="Seminar")
    clean_target = Schedule(day="Wednesday", time=time(12), odd_or_even="even", type="Seminar")
    repo.session.add_all([source, clean_target])
    repo.session.flush()
    movable = ScheduleGroupLink(group_id=other.id, schedule_id=source.id)
    repo.session.add(movable)
    repo.session.commit()

    with pytest.raises(IntegrityError, match="historical group links are immutable"):
        repo.session.execute(
            text("UPDATE schedulegrouplinks SET schedule_id = :target WHERE id = :link"),
            {"target": historical.id, "link": movable.id},
        )
    repo.session.rollback()
    assert OrmService(repo.session, auto_commit=False).update(
        movable, {"schedule_id": historical.id}
    ) is None
    assert repo.session.get(ScheduleGroupLink, movable.id).schedule_id == source.id
    assert repo.session.get(ScheduleGroupLink, historical_link.id).schedule_id == historical.id
    assert repo.session.get(Lesson, past.id).schedule_id == historical.id

    repo.session.execute(
        text("UPDATE schedulegrouplinks SET schedule_id = :target WHERE id = :link"),
        {"target": clean_target.id, "link": movable.id},
    )
    repo.session.commit()
    repo.session.expire_all()
    assert repo.session.get(ScheduleGroupLink, movable.id).schedule_id == clean_target.id


def test_database_rejects_lesson_outside_closed_version(repo):
    schedule, group, _, _, _, past, _ = _schedule(repo)
    _update(repo, schedule, [group], day="Tuesday")
    with pytest.raises(IntegrityError, match="outside schedule version"):
        repo.session.add(Lesson(schedule_id=schedule.id, date=SWITCH))
        repo.session.flush()
    repo.session.rollback()
    assert repo.session.get(Lesson, past.id).date < SWITCH


def test_repository_clear_cannot_erase_lesson_history(repo):
    schedule, _, _, link, _, past, _ = _schedule(repo)
    with pytest.raises(repository_module.RepositoryError, match="lesson history"):
        repo.clear_database()
    assert repo.session.get(Schedule, schedule.id) is not None
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.get(Lesson, past.id) is not None


def test_group_and_student_deletion_cannot_cascade_into_history(repo):
    schedule, group, _, link, student, past, _ = _schedule(repo)
    service = OrmService(repo.session, auto_commit=False)
    with pytest.raises(repository_module.RepositoryError, match="lesson results"):
        repo.delete_student(student)
    with pytest.raises(repository_module.RepositoryError, match="lesson history"):
        repo.delete_group(group)
    assert service.delete(student) is None
    assert service.delete(group) is None
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.get(Lesson, past.id) is not None
    assert repo.session.get(Schedule, schedule.id) is not None
