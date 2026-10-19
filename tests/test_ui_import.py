from datetime import date, time

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.models import Group, Lesson, Schedule, ScheduleGroupLink, Student
from app.ui.data import repository as repository_module
from app.io_tools.xlsx_config import XLSX_COLUMNS_BY_SHEET
from app.io_tools.application.multisheet_smart_import import MultiSheetSmartImporter
from app.io_tools.application.human_table_import import HumanTableImporter
from app.services.ormservice import OrmService, OrmServiceError
from app.ui.data.repository import ImportPreview, RepositoryError


def _workbook(path):
    workbook = Workbook()
    workbook.active.title = "Noise"
    workbook.active.append(["Random", "Unrelated"])
    workbook.active.append(["nothing", "useful"])
    return workbook


def test_legacy_schedule_workbook_is_rejected_before_import(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'legacy.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "schedules"
    sheet.append(["id", "odd_or_even", "type", "day", "time"])
    sheet.append([1, "even", "Seminar", "Monday", "10:00"])
    source = tmp_path / "old.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        with pytest.raises(RepositoryError, match="legacy format"):
            repo.preview_import_from_xlsx(source, strategy="standard")
        legacy_result = MultiSheetSmartImporter(repo.session).import_workbook(source)
        assert any("version-aware" in error for error in legacy_result.errors)
        assert repo.session.scalar(select(Schedule.id)) is None
    finally:
        repo.close()
        repo.engine.dispose()


def test_versioned_schedule_workbook_restores_only_into_empty_database(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'source.db'}")
    source_repo = repository_module.DiaryRepository()
    group = Group(name="IU7-11")
    schedule = Schedule(
        day="Monday", time=time(10), odd_or_even="even", type="Seminar",
        effective_from=date(2026, 2, 1),
    )
    source_repo.session.add_all([group, schedule])
    source_repo.session.flush()
    source_repo.session.add(ScheduleGroupLink(group_id=group.id, schedule_id=schedule.id))
    source_repo.session.flush()
    source_repo.session.add(Lesson(schedule_id=schedule.id, date=date(2026, 2, 2), topic="First"))
    source_repo.session.commit()
    source = tmp_path / "versioned.xlsx"
    source_repo.export_to_xlsx(source)
    source_repo.close()
    source_repo.engine.dispose()

    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'target.db'}")
    target_repo = repository_module.DiaryRepository()
    try:
        with pytest.raises(OrmServiceError, match="version-aware"):
            OrmService(target_repo.session, auto_commit=False).import_from_xlsx(source)
        preview = target_repo.preview_import_from_xlsx(source, strategy="standard")
        assert not preview.errors
        assert target_repo.import_from_preview(preview)["schedules"] == 1
        restored = target_repo.session.scalar(select(Schedule))
        assert (restored.series_key, restored.revision, restored.effective_from) == (
            schedule.series_key, 1, date(2026, 2, 1)
        )
        assert target_repo.session.scalar(select(Lesson)).topic == "First"
        with pytest.raises(RepositoryError, match="empty database"):
            target_repo.import_from_preview(preview)
        assert target_repo.session.scalar(select(Schedule.id)) == restored.id
    finally:
        target_repo.close()
        target_repo.engine.dispose()


def test_manually_supplied_legacy_schedule_preview_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'manual.db'}")
    repo = repository_module.DiaryRepository()
    try:
        preview = ImportPreview(
            source_path=tmp_path / "missing.xlsx", strategy="standard", mode="merge",
            data={"schedules": [{"day": "Monday", "time": "10:00"}]},
        )
        with pytest.raises(RepositoryError, match="Legacy schedule rows"):
            repo.import_from_preview(preview)
        assert repo.session.scalar(select(Schedule.id)) is None
    finally:
        repo.close()
        repo.engine.dispose()


def test_replace_import_cannot_erase_existing_lesson_history(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'replace.db'}")
    repo = repository_module.DiaryRepository()
    schedule = Schedule(day="Monday", time=time(10), odd_or_even="even", type="Seminar")
    repo.session.add(schedule)
    repo.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=date(2026, 2, 2), topic="Saved")
    repo.session.add(lesson)
    repo.session.commit()
    try:
        preview = ImportPreview(
            source_path=tmp_path / "unused.xlsx", strategy="smart", mode="replace",
            data={"groups": [{"name": "IU7-11"}]},
        )
        with pytest.raises(RepositoryError, match="delete lesson history"):
            repo.import_from_preview(preview)
        assert repo.session.get(Lesson, lesson.id).topic == "Saved"
    finally:
        repo.close()
        repo.engine.dispose()


def test_human_table_marks_link_groups_before_creating_lesson(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'human.db'}")
    workbook = Workbook()
    groups = workbook.active
    groups.title = "Groups"
    groups.append(["group", "speciality"])
    groups.append(["IU7-11", "CS"])
    students = workbook.create_sheet("Students")
    students.append(["surname", "first name", "group"])
    students.append(["Ivanov", "Ivan", "IU7-11"])
    marks = workbook.create_sheet("Marks")
    marks.append(["student", "mark"])
    marks.append(["Ivanov Ivan", 87])
    source = tmp_path / "human.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        result = HumanTableImporter(repo.session).import_workbook(source)
        assert result.errors == []
        assert repo.session.scalar(select(Lesson.id)) is not None
        assert repo.session.scalar(select(ScheduleGroupLink.id)) is not None
        repeated = HumanTableImporter(repo.session).import_workbook(source)
        assert repeated.errors == []
        assert len(repo.session.scalars(select(Lesson)).all()) == 1
    finally:
        repo.close()
        repo.engine.dispose()


def test_smart_preview_imports_only_groups_and_students(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'smart.db'}")
    workbook = _workbook(tmp_path)
    groups = workbook.create_sheet("Roster")
    groups.append(["Группа", "Специальность"])
    groups.append(["IU7-11", "Computer science"])
    students = workbook.create_sheet("People")
    students.append(["Фамилия", "Имя", "Группа", "Почта"])
    students.append(["Ivanov", "Ivan", "IU7-11", "ivan@example.org"])
    marks = workbook.create_sheet("marks")
    marks.append(["student_id", "lesson_id", "data"])
    marks.append([1, 1, 80])
    source = tmp_path / "smart.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert preview.row_counts == {"groups": 1, "students": 1}
        assert repo.import_from_preview(preview) == {"groups": 1, "students": 1}
        student = repo.session.scalar(select(Student))
        assert student.bmstu_email == "ivan@example.org"
        assert repo.session.scalar(select(Group)).name == "IU7-11"
    finally:
        repo.close()


def test_template_preview_finds_model_table_and_skips_noise(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'template.db'}")
    workbook = _workbook(tmp_path)
    sheet = workbook.create_sheet("Somewhere")
    sheet["C5"] = "name"
    sheet["D5"] = "speciality"
    sheet["C6"] = "IU7-12"
    sheet["D6"] = "Mathematics"
    source = tmp_path / "template.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        preview = repo.preview_import_from_xlsx(source, strategy="template")
        assert preview.row_counts == {"groups": 1}
        assert repo.import_from_preview(preview) == {"groups": 1}
        assert repo.session.scalar(select(Group)).name == "IU7-12"
    finally:
        repo.close()


def test_smart_merge_updates_existing_student_without_erasing_optional_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'merge.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Roster"
    sheet.append(["Фамилия", "Имя", "Группа", "Почта"])
    sheet.append(["Ivanov", "Ivan", "IU7-11", "ivan@example.org"])
    source = tmp_path / "merge.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        repo.import_from_preview(repo.preview_import_from_xlsx(source, strategy="smart"))
        student = repo.session.scalar(select(Student))
        student.patronymic = "Ivanovich"
        repo.session.commit()
        sheet["D2"] = "new@example.org"
        workbook.save(source)
        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert preview.row_counts == {"students": 1}
        repo.import_from_preview(preview)
        assert len(repo.session.scalars(select(Student)).all()) == 1
        student = repo.session.scalar(select(Student))
        assert student.bmstu_email == "new@example.org"
        assert student.patronymic == "Ivanovich"
    finally:
        repo.close()


def test_standard_preview_rejects_invalid_data_before_import(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'strict.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "groups"
    sheet.append(XLSX_COLUMNS_BY_SHEET["groups"])
    sheet.append([None, None, None, None, None])
    sheet.append([None, "IU7-11", None, None, None])
    students = workbook.create_sheet("students")
    students.append(XLSX_COLUMNS_BY_SHEET["students"])
    students.append([None, "not-an-id", "Ivanov", "Ivan", None, None, None, None, None])
    source = tmp_path / "strict.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        preview = repo.preview_import_from_xlsx(source, strategy="standard")
        assert preview.errors
        assert repo.session.scalars(select(Group)).all() == []
    finally:
        repo.close()


def test_template_accepts_missing_optional_email_and_skips_missing_group(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'optional.db'}")
    workbook = Workbook()
    groups = workbook.active
    groups.title = "Groups"
    groups.append(["name", "speciality"])
    groups.append(["IU7-11", "Math"])
    students = workbook.create_sheet("Students")
    students.append(["group_id", "surname", "first_name"])
    students.append([1, "Ivanov", "Ivan"])
    students.append([None, "Petrov", "Petr"])
    source = tmp_path / "optional.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        preview = repo.preview_import_from_xlsx(source, strategy="template")
        assert preview.row_counts == {"groups": 1, "students": 1}
        assert preview.warnings
        repo.import_from_preview(preview)
        student = repo.session.scalar(select(Student))
        assert student.surname == "Ivanov"
        assert student.bmstu_email is None
    finally:
        repo.close()


def test_standard_merge_remaps_foreign_ids_and_is_repeatable(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'foreign.db'}")
    workbook = Workbook()
    groups = workbook.active
    groups.title = "groups"
    groups.append(XLSX_COLUMNS_BY_SHEET["groups"])
    groups.append([1, "REMOTE", "Physics", None, None])
    students = workbook.create_sheet("students")
    students.append(XLSX_COLUMNS_BY_SHEET["students"])
    students.append([1, 1, "New", "Person", None, None, None, None, None])
    source = tmp_path / "foreign.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        repo.session.add(Group(name="LOCAL", speciality="Local subject"))
        repo.session.flush()
        repo.session.add(Student(group_id=1, surname="Local", first_name="Student"))
        repo.session.commit()

        for _ in range(2):
            preview = repo.preview_import_from_xlsx(source, strategy="standard")
            assert preview.errors == []
            repo.import_from_preview(preview)

        local_group = repo.session.scalar(select(Group).where(Group.name == "LOCAL"))
        imported_group = repo.session.scalar(select(Group).where(Group.name == "REMOTE"))
        imported_student = repo.session.scalar(
            select(Student).where(Student.surname == "New")
        )
        assert local_group.id == 1
        assert local_group.speciality == "Local subject"
        assert imported_group.id != local_group.id
        assert imported_student.group_id == imported_group.id
        assert len(repo.session.scalars(select(Student)).all()) == 2
    finally:
        repo.close()


def test_empty_optional_cell_preserves_existing_value(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'blank.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Students"
    sheet.append(["group_id", "surname", "first_name", "bmstu_email"])
    sheet.append([1, "Ivanov", "Ivan", None])
    source = tmp_path / "blank.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        repo.session.add(Group(name="IU7-11"))
        repo.session.flush()
        repo.session.add(Student(
            group_id=1, surname="Ivanov", first_name="Ivan",
            bmstu_email="saved@example.org",
        ))
        repo.session.commit()

        preview = repo.preview_import_from_xlsx(source, strategy="template")
        assert preview.row_counts == {"students": 1}
        repo.import_from_preview(preview)
        assert repo.session.scalar(select(Student)).bmstu_email == "saved@example.org"
    finally:
        repo.close()


def test_smart_preview_rejects_ambiguous_student_match(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'ambiguous.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Roster"
    sheet.append(["Фамилия", "Имя", "Группа", "Почта"])
    sheet.append(["Ivanov", "Ivan", "IU7-11", None])
    source = tmp_path / "ambiguous.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        repo.session.add(Group(name="IU7-11"))
        repo.session.flush()
        repo.session.add_all([
            Student(group_id=1, surname="Ivanov", first_name="Ivan", bmstu_email="one@example.org"),
            Student(group_id=1, surname="Ivanov", first_name="Ivan", bmstu_email="two@example.org"),
        ])
        repo.session.commit()

        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert "multiple students" in preview.errors[0]
        sheet["D2"] = "two@example.org"
        workbook.save(source)
        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert preview.errors == []
        repo.import_from_preview(preview)
        assert len(repo.session.scalars(select(Student)).all()) == 2
    finally:
        repo.close()


def test_smart_preview_rejects_conflicting_identifiers(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'conflict.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Roster"
    sheet.append(["Фамилия", "Имя", "Группа", "Почта", "Личное дело"])
    sheet.append(["Ivanov", "Ivan", "IU7-11", "two@example.org", "A1"])
    source = tmp_path / "conflict.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        repo.session.add(Group(name="IU7-11"))
        repo.session.flush()
        repo.session.add_all([
            Student(group_id=1, surname="Ivanov", first_name="Ivan", bmstu_email="one@example.org", personal_data="A1"),
            Student(group_id=1, surname="Petrov", first_name="Petr", bmstu_email="two@example.org", personal_data="B2"),
        ])
        repo.session.commit()

        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert "different students" in preview.errors[0]
    finally:
        repo.close()


def test_smart_rejects_different_patronymic_before_updating(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'patronymic.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Roster"
    sheet.append(["Фамилия", "Имя", "Отчество", "Группа", "Почта"])
    sheet.append(["Ivanov", "Ivan", "Sergeevich", "IU7-11", None])
    source = tmp_path / "patronymic.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        repo.session.add(Group(name="IU7-11"))
        repo.session.flush()
        repo.session.add(Student(
            group_id=1, surname="Ivanov", first_name="Ivan",
            patronymic="Petrovich", bmstu_email="ivan@example.org",
        ))
        repo.session.commit()

        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert "patronymic differs" in preview.errors[0]
        assert repo.session.scalar(select(Student)).patronymic == "Petrovich"

        sheet["E2"] = "ivan@example.org"
        workbook.save(source)
        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert "patronymic conflicts" in preview.errors[0]
    finally:
        repo.close()


def test_smart_fills_missing_patronymic_for_identified_student(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'fill_patronymic.db'}")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Roster"
    sheet.append(["Фамилия", "Имя", "Отчество", "Группа", "Почта"])
    sheet.append(["Ivanov", "Ivan", "Sergeevich", "IU7-11", "ivan@example.org"])
    source = tmp_path / "fill_patronymic.xlsx"
    workbook.save(source)

    repo = repository_module.DiaryRepository()
    try:
        repo.session.add(Group(name="IU7-11"))
        repo.session.flush()
        repo.session.add(Student(
            group_id=1, surname="Ivanov", first_name="Ivan",
            patronymic=None, bmstu_email="ivan@example.org",
        ))
        repo.session.commit()

        preview = repo.preview_import_from_xlsx(source, strategy="smart")
        assert preview.errors == []
        repo.import_from_preview(preview)
        students = repo.session.scalars(select(Student)).all()
        assert len(students) == 1
        assert students[0].patronymic == "Sergeevich"
    finally:
        repo.close()
