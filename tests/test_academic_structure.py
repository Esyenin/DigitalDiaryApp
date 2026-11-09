"""Academic configuration regression tests use disposable SQLite files only."""

from datetime import date, time, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models import AcademicTerm, AcademicYear, CourseOfferingGroup, Lesson, Schedule, TeachingModule
from app.ui.data import repository as repository_module
from app.ui.data.academic_migration import ensure_academic_schema
from app.ui.data.calendar import SemesterSettings


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'academic.db'}")
    repository = repository_module.DiaryRepository()
    yield repository
    repository.close()
    repository.engine.dispose()


def test_multiple_years_terms_courses_and_modules(repo):
    first = repo.academic_action("create_year", "2026/27", date(2026, 9, 1), date(2027, 9, 1))
    second = repo.academic_action("create_year", "2027/28", date(2027, 9, 1), date(2028, 9, 1))
    term = repo.academic_action("create_term", first.id, "Autumn", date(2026, 9, 7), 17)
    later = repo.academic_action("create_term", second.id, "Autumn", date(2027, 9, 6), 17)
    groups = [repo.create_group(name, None) for name in ("A", "B")]
    discipline = repo.academic_action("create_discipline", "Algorithms")
    course = repo.academic_action("create_offering", term.id, discipline.id, "Shared course", [g.id for g in groups])
    repo.academic_action("create_offering", later.id, discipline.id, "Next year", [groups[0].id])
    module = repo.academic_action("create_module", course.id, "First", 1, date(2026, 9, 7), date(2026, 11, 2))
    assert module.offering_id == course.id
    assert set(repo.session.scalars(select(CourseOfferingGroup.group_id).where(
        CourseOfferingGroup.offering_id == course.id))) == {group.id for group in groups}
    repo.academic_action("select_term", term.id)
    assert repo.academic_calendar() == SemesterSettings(date(2026, 9, 7), 17)


def test_module_overlap_rolls_back_and_closed_terms_reject_configuration(repo):
    year = repo.academic_action("create_year", "Year", date(2026, 9, 1), date(2027, 9, 1))
    term = repo.academic_action("create_term", year.id, "Term", date(2026, 9, 7), 17)
    discipline = repo.academic_action("create_discipline", "Course")
    group = repo.create_group("Group", None)
    course = repo.academic_action("create_offering", term.id, discipline.id, "Offering", [group.id])
    repo.academic_action("create_module", course.id, "One", 1, date(2026, 9, 7), date(2026, 11, 2))
    with pytest.raises(repository_module.RepositoryError, match="overlap"):
        repo.academic_action("create_module", course.id, "Two", 2, date(2026, 10, 1), date(2026, 12, 1))
    assert len(list(repo.session.scalars(select(TeachingModule)))) == 1
    repo.academic_action("close_term", term.id)
    with pytest.raises(repository_module.RepositoryError, match="closed"):
        repo.academic_action("create_offering", term.id, discipline.id, "Other", [group.id])
    with pytest.raises(IntegrityError, match="immutable"):
        repo.session.execute(update(AcademicTerm).where(AcademicTerm.id == term.id).values(status="open"))
    repo.session.rollback()


def test_legacy_calendar_import_is_once_and_academic_export_contains_context(repo, tmp_path):
    old = SemesterSettings(date(2026, 2, 2), 17)
    repo.academic_action("import_legacy_calendar", old)
    repo.academic_action("import_legacy_calendar", SemesterSettings(date(2027, 2, 1), 18))
    assert repo.academic_calendar() == old
    assert len(list(repo.session.scalars(select(AcademicYear)))) == 1
    path = repo.export_to_xlsx(tmp_path / "complete.xlsx")
    preview = repo.preview_import_from_xlsx(path, strategy="standard")
    from app.ui.data.teaching_archive import VERSION
    assert preview.archive_version == VERSION
    assert preview.data["academic_terms"][0]["origin"] == "legacy_settings"
    assert len(preview.data["academic_years"]) == 1


def test_migration_repeated_preserves_existing_records(repo):
    schedule = Schedule(day="Monday", time=time(10), type="Seminar", odd_or_even="even")
    repo.session.add(schedule)
    repo.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=date(2026, 9, 7), topic="Preserve")
    repo.session.add(lesson)
    repo.session.commit()
    ids = (schedule.id, lesson.id)
    repo.session.rollback()
    ensure_academic_schema(repo.engine)
    ensure_academic_schema(repo.engine)
    repo.refresh()
    assert (schedule.id, lesson.id) == ids
    assert schedule.offering_id is None
    assert lesson.topic == "Preserve"


def test_academic_qt_workspace_is_accessible(repo, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app.ui.windows.academic_workspace import AcademicWorkspace
    from app.ui.windows.ui_MainWindowsUI import MainWindow

    monkeypatch.setattr(repository_module, "DATABASE_URL", repo.engine.url.render_as_string())
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.show_academic_workspace()
        workspace = window.detail_page.findChild(AcademicWorkspace)
        assert workspace is not None
        assert workspace.tabs.count() == 5
    finally:
        window.close()
        app.processEvents()


def test_multigroup_schedule_uses_course_calendar_and_keeps_legacy_ids(repo):
    start = date.today() + timedelta(days=7 - date.today().weekday())
    year = repo.academic_action("create_year", "Future year", start, start + timedelta(weeks=52))
    term = repo.academic_action("create_term", year.id, "Future term", start, 4)
    discipline = repo.academic_action("create_discipline", "Shared discipline")
    groups = [repo.create_group(name, None) for name in ("Shared A", "Shared B")]
    course = repo.academic_action("create_offering", term.id, discipline.id, "Shared offering", [g.id for g in groups])
    schedule = repo.create_schedule(None, groups, "Monday", time(10), "even", "Seminar", False,
                                    SemesterSettings(date(2020, 2, 3), 1),
                                    effective_from=start, offering_id=course.id)
    lessons = list(repo.session.scalars(select(Lesson).where(Lesson.schedule_id == schedule.id)))
    assert [lesson.date for lesson in lessons] == [start, start + timedelta(weeks=2)]
    assert len(schedule.group_links) == 2
    with pytest.raises(IntegrityError, match="immutable"):
        repo.session.execute(update(Schedule).where(Schedule.id == schedule.id).values(offering_id=None))
    repo.session.rollback()
    assert schedule.offering_id == course.id
