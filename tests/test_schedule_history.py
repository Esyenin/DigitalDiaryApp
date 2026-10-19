from datetime import date, time

import pytest
from sqlalchemy import select

from app.models import Attendance, Comment, Group, Lesson, Mark, Schedule, ScheduleGroupLink, Student
from app.ui.data import repository as repository_module
from app.ui.data.calendar import SemesterSettings


TODAY = date(2026, 2, 10)
SETTINGS = SemesterSettings(start_date=date(2026, 2, 2), total_weeks=4)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(
        repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'history.db'}"
    )
    repository = repository_module.DiaryRepository()
    yield repository
    repository.close()
    repository.engine.dispose()


def _schedule(repo, *, lesson_date=None, topic=None, result_types=()):
    group = Group(name="IU7-11")
    other_group = Group(name="IU7-12")
    schedule = Schedule(
        day="Monday", time=time(10), odd_or_even="even",
        type="Seminar", is_assessment=False,
    )
    repo.session.add_all([group, other_group, schedule])
    repo.session.flush()
    link = ScheduleGroupLink(group_id=group.id, schedule_id=schedule.id)
    repo.session.add(link)
    student = Student(group_id=group.id, surname="Ivanov", first_name="Ivan")
    repo.session.add(student)
    repo.session.flush()

    lesson = None
    if lesson_date is not None:
        lesson = Lesson(schedule_id=schedule.id, date=lesson_date, topic=topic)
        repo.session.add(lesson)
        repo.session.flush()
        if "attendance" in result_types:
            repo.session.add(Attendance(student_id=student.id, lesson_id=lesson.id, is_visited=True))
        if "mark" in result_types:
            repo.session.add(Mark(student_id=student.id, lesson_id=lesson.id, data=87))
        if "comment" in result_types:
            repo.session.add(Comment(student_id=student.id, lesson_id=lesson.id, data="Passed"))
    repo.session.commit()
    return schedule, group, other_group, link, lesson


def _update(repo, schedule, groups, **changes):
    values = {
        "day": "Monday", "lesson_time": time(10), "week_type": "even",
        "lesson_type": "Seminar", "is_assessment": False,
    }
    values.update(changes)
    repo.update_schedule(
        schedule, None, groups, settings=SETTINGS, as_of=TODAY, **values
    )


@pytest.mark.parametrize(
    "change",
    [
        {"day": "Tuesday"},
        {"week_type": "odd"},
        {"lesson_time": time(12)},
        {"lesson_type": "Lab Work"},
        {"is_assessment": True},
        {"groups": "other"},
    ],
)
def test_historical_results_survive_rejected_schedule_edits(repo, change):
    schedule, group, other_group, link, lesson = _schedule(
        repo, lesson_date=date(2026, 2, 9), topic="Lesson 1",
        result_types=("attendance", "mark", "comment"),
    )
    groups = [other_group] if change.pop("groups", None) else [group]
    ids = {
        "schedule": schedule.id, "link": link.id, "lesson": lesson.id,
        "attendance": repo.session.scalar(select(Attendance.id)),
        "mark": repo.session.scalar(select(Mark.id)),
        "comment": repo.session.scalar(select(Comment.id)),
    }

    with pytest.raises(repository_module.RepositoryError, match="Historical data takes priority"):
        _update(repo, schedule, groups, **change)

    repo.session.expire_all()
    saved_schedule = repo.session.get(Schedule, ids["schedule"])
    assert (saved_schedule.day, saved_schedule.time, saved_schedule.odd_or_even) == (
        "Monday", time(10), "even"
    )
    assert (saved_schedule.type, saved_schedule.is_assessment) == ("Seminar", False)
    assert repo.session.get(ScheduleGroupLink, ids["link"]).group_id == group.id
    saved_lesson = repo.session.get(Lesson, ids["lesson"])
    assert (saved_lesson.date, saved_lesson.topic) == (date(2026, 2, 9), "Lesson 1")
    assert repo.session.get(Attendance, ids["attendance"]).is_visited is True
    assert repo.session.get(Mark, ids["mark"]).data == 87
    assert repo.session.get(Comment, ids["comment"]).data == "Passed"


def test_historical_lesson_blocks_schedule_deletion(repo):
    schedule, _, _, link, lesson = _schedule(
        repo, lesson_date=date(2026, 2, 9), result_types=("attendance", "mark", "comment")
    )
    with pytest.raises(repository_module.RepositoryError, match="Historical data takes priority"):
        repo.delete_schedule(schedule, as_of=TODAY)
    repo.session.expire_all()
    assert repo.session.get(Schedule, schedule.id) is not None
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert repo.session.get(Lesson, lesson.id) is not None
    assert repo.session.scalar(select(Attendance.id)) is not None
    assert repo.session.scalar(select(Mark.id)) is not None
    assert repo.session.scalar(select(Comment.id)) is not None


@pytest.mark.parametrize("lesson_date", [date(2026, 2, 9), TODAY])
def test_past_or_today_lesson_is_protected_without_results(repo, lesson_date):
    schedule, group, _, _, lesson = _schedule(repo, lesson_date=lesson_date)
    with pytest.raises(repository_module.RepositoryError, match="Historical data takes priority"):
        _update(repo, schedule, [group], day="Tuesday")
    with pytest.raises(repository_module.RepositoryError, match="Historical data takes priority"):
        repo.delete_schedule(schedule, as_of=TODAY)
    assert repo.session.get(Lesson, lesson.id).date == lesson_date


@pytest.mark.parametrize("result_type", ["attendance", "mark", "comment", "topic"])
def test_future_lesson_with_content_is_protected(repo, result_type):
    schedule, group, _, _, lesson = _schedule(
        repo,
        lesson_date=date(2026, 2, 16),
        topic="Future topic" if result_type == "topic" else None,
        result_types=() if result_type == "topic" else (result_type,),
    )
    with pytest.raises(repository_module.RepositoryError, match="Historical data takes priority"):
        _update(repo, schedule, [group], day="Tuesday")
    with pytest.raises(repository_module.RepositoryError, match="Historical data takes priority"):
        repo.delete_schedule(schedule, as_of=TODAY)
    assert repo.session.get(Lesson, lesson.id) is not None


def test_future_empty_lesson_can_be_regenerated(repo):
    schedule, group, _, _, old_lesson = _schedule(repo, lesson_date=date(2026, 2, 16))
    _update(repo, schedule, [group], day="Tuesday")
    assert repo.session.scalar(
        select(Lesson.id).where(Lesson.schedule_id == schedule.id, Lesson.date == old_lesson.date)
    ) is None
    assert schedule.day == "Tuesday"
    assert all(lesson.date.weekday() == 1 for lesson in schedule.lessons)


def test_unused_schedule_can_be_deleted(repo):
    schedule, _, _, link, _ = _schedule(repo)
    repo.delete_schedule(schedule, as_of=TODAY)
    assert repo.session.get(Schedule, schedule.id) is None
    assert repo.session.get(ScheduleGroupLink, link.id) is None


def test_unchanged_schedule_keeps_group_link_ids(repo):
    schedule, group, _, link, lesson = _schedule(repo, lesson_date=date(2026, 2, 9))
    _update(repo, schedule, [group])
    assert repo.session.get(ScheduleGroupLink, link.id) is not None
    assert [item.id for item in schedule.group_links] == [link.id]
    assert repo.session.get(Lesson, lesson.id) is not None


def test_future_whitespace_topic_does_not_block_deletion(repo):
    schedule, _, _, _, lesson = _schedule(repo, lesson_date=date(2026, 2, 16), topic="  ")
    repo.delete_schedule(schedule, as_of=TODAY)
    assert repo.session.get(Lesson, lesson.id) is None
