"""
Тесты слоя io_tools.
"""
from datetime import date, datetime, time
import logging
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pydantic import BaseModel

from app.io_tools import ImportExportService, XlsxExporter, XlsxImporter
from app.io_tools.xlsx_config import XLSX_COLUMNS_BY_SHEET, XLSX_SHEETS_ORDER
from app.models import (
    Attendance,
    Comment,
    Group,
    Lesson,
    Mark,
    Schedule,
    ScheduleGroupLink,
    Student,
)
from app.services import OrmService


class SampleSchema(BaseModel):
    """
    Вспомогательная схема для тестов io_tools.
    """

    id: int
    title: str


def _logs_dir() -> Path:
    """
    Возвращает путь к директории логов проекта.

    :return: Абсолютный путь к папке `logs` в корне проекта.
    """
    return Path(__file__).resolve().parents[1] / "logs"


def _normalize_db_row(row: object, sheet_name: str) -> dict[str, object]:
    """
    Преобразует ORM-объект в словарь значений по конфигурации XLSX-листа.

    :param row: ORM-объект, представляющий строку таблицы.
    :param sheet_name: Каноническое имя XLSX-листа для этой модели.
    :return: Словарь значений в порядке и составе, используемом для экспорта.
    """
    return {
        column_name: getattr(row, column_name)
        for column_name in XLSX_COLUMNS_BY_SHEET[sheet_name]
    }


def _sorted_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """
    Сортирует строки листа по идентификатору для стабильного сравнения.

    :param rows: Список строк одного листа.
    :return: Новый список строк, отсортированный по полю `id`.
    """
    return sorted(rows, key=lambda row: row["id"])


def _normalize_imported_rows(
    imported_rows: list[dict[str, object]],
    expected_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """
    Приводит импортированные из XLSX значения к виду, пригодному для точного сравнения.

    Excel иногда возвращает дату как `datetime` с нулевым временем. Для round-trip
    проверки это не считается искажением данных, поэтому функция нормализует такие
    значения по типу соответствующего поля из ожидаемой строки.

    :param imported_rows: Строки, считанные из XLSX-файла.
    :param expected_rows: Эталонные строки, собранные из ORM-объектов БД.
    :return: Новый список импортированных строк после нормализации типов значений.
    """
    normalized_rows: list[dict[str, object]] = []

    for imported_row, expected_row in zip(
        _sorted_rows(imported_rows),
        _sorted_rows(expected_rows),
        strict=True,
    ):
        normalized_row: dict[str, object] = {}

        for key, imported_value in imported_row.items():
            expected_value = expected_row[key]
            if (
                isinstance(imported_value, datetime)
                and isinstance(expected_value, date)
                and not isinstance(expected_value, datetime)
            ):
                normalized_row[key] = imported_value.date()
            else:
                normalized_row[key] = imported_value

        normalized_rows.append(normalized_row)

    return normalized_rows


def test_xlsx_exporter_exports_full_and_partial_payloads(tmp_path):
    """
    Один и тот же метод экспортирует как полный, так и частичный набор листов.
    """
    exporter = XlsxExporter()
    full_path = tmp_path / "full_export.xlsx"
    partial_path = tmp_path / "partial_export.xlsx"

    full_payload = {
        "groups": [
            {
                "id": 1,
                "name": "IU7-11",
                "speciality": "09.03.01_Informatics",
                "created_at": datetime(2026, 5, 10, 12, 30, 0),
            },
            Group(name="IU7-12", speciality="09.03.02_Applied"),
        ],
        "lessons": [
            {
                "id": 3,
                "date": date(2026, 5, 10),
                "time": time(9, 0),
                "topic": "SQLAlchemy",
            }
        ],
    }
    partial_payload = {
        "groups": full_payload["groups"],
    }

    exporter.export(full_payload, full_path)
    exporter.export(partial_payload, partial_path)

    full_workbook = load_workbook(full_path)
    partial_workbook = load_workbook(partial_path)

    assert full_workbook.sheetnames == ["groups", "lessons"]
    assert partial_workbook.sheetnames == ["groups"]

    groups_sheet = full_workbook["groups"]
    assert groups_sheet.cell(1, 1).value == "id"
    assert groups_sheet.cell(1, 2).value == "name"
    assert groups_sheet.cell(2, 2).value == "IU7-11"
    assert groups_sheet.cell(3, 2).value == "IU7-12"

    lessons_sheet = full_workbook["lessons"]
    assert lessons_sheet.cell(1, 2).value == "schedule_id"
    assert lessons_sheet.cell(1, 3).value == "topic"
    assert lessons_sheet.cell(1, 4).value == "date"
    assert lessons_sheet.cell(2, 3).value == "SQLAlchemy"


def test_xlsx_exporter_uses_global_sheet_order(tmp_path):
    """
    При полном или смешанном экспорте известные листы идут в порядке конфигурации.
    """
    exporter = XlsxExporter()
    file_path = tmp_path / "ordered_export.xlsx"
    payload = {
        "students": [{"id": 1, "surname": "Petrov", "first_name": "Petr"}],
        "groups": [{"id": 1, "name": "IU7-11"}],
        "custom": [{"value": "note"}],
        "comments": [{"id": 1, "student_id": 1, "lesson_id": 1}],
    }

    exporter.export(payload, file_path)
    workbook = load_workbook(file_path)

    assert workbook.sheetnames == ["groups", "students", "comments", "custom"]


def test_xlsx_exporter_supports_schema_rows(tmp_path):
    """
    Экспортер принимает строки в виде схем и обычных словарей.
    """
    exporter = XlsxExporter()
    file_path = tmp_path / "schema_export.xlsx"
    payload = {
        "meta": [
            SampleSchema(id=1, title="Header"),
            {"id": 2, "title": "Body"},
        ]
    }

    saved_path = exporter.export(payload, file_path)
    workbook = load_workbook(saved_path)
    meta_sheet = workbook["meta"]

    assert isinstance(saved_path, Path)
    assert meta_sheet.cell(1, 1).value == "id"
    assert meta_sheet.cell(1, 2).value == "title"
    assert meta_sheet.cell(2, 2).value == "Header"
    assert meta_sheet.cell(3, 2).value == "Body"


def test_xlsx_exporter_rejects_empty_payload(tmp_path):
    """
    Пустой экспортный набор считается ошибкой.
    """
    exporter = XlsxExporter()

    with pytest.raises(
        ValueError,
        match="Для экспорта нужно передать хотя бы один лист.",
    ):
        exporter.export({}, tmp_path / "empty.xlsx")


def test_xlsx_importer_reads_known_sheets_in_configured_order(tmp_path):
    """
    Импортер читает листы в порядке XLSX-конфигурации и пропускает пустые строки.
    """
    exporter = XlsxExporter()
    importer = XlsxImporter()
    file_path = tmp_path / "importable_export.xlsx"
    payload = {
        "students": [
            {"id": 1, "group_id": 1, "surname": "Petrov", "first_name": "Petr"},
            {"id": None, "group_id": None, "surname": None, "first_name": None},
        ],
        "groups": [{"id": 1, "name": "IU7-11", "speciality": "09.03.01"}],
    }

    exporter.export(payload, file_path)
    imported = importer.import_data(file_path)

    assert list(imported) == ["groups", "students"]
    assert imported["groups"][0]["name"] == "IU7-11"
    assert imported["students"][0]["surname"] == "Petrov"
    assert len(imported["students"]) == 1


def test_xlsx_importer_rejects_unknown_sheet(tmp_path):
    """
    Импортер отклоняет файл с неизвестным листом.
    """
    exporter = XlsxExporter()
    importer = XlsxImporter()
    file_path = tmp_path / "unknown_sheet.xlsx"
    payload = {
        "custom": [{"value": "note"}],
    }

    exporter.export(payload, file_path)

    with pytest.raises(
        ValueError,
        match="Неизвестные листы в XLSX-файле: custom.",
    ):
        importer.import_data(file_path)


def test_xlsx_importer_rejects_missing_required_columns(tmp_path):
    """
    Импортер проверяет наличие обязательных колонок.
    """
    exporter = XlsxExporter()
    importer = XlsxImporter()
    file_path = tmp_path / "missing_headers.xlsx"
    payload = {
        "students": [{"id": 1, "surname": "Petrov"}],
    }

    exporter.export(payload, file_path)
    workbook = load_workbook(file_path)
    worksheet = workbook["students"]
    worksheet.delete_cols(2, 3)
    workbook.save(file_path)

    with pytest.raises(
        ValueError,
        match="В листе students отсутствуют обязательные колонки: group_id, surname, first_name.",
    ):
        importer.import_data(file_path)


def test_import_export_service_delegates_export_and_import(tmp_path):
    """
    Верхнеуровневый сервис делегирует экспорт и импорт XLSX соответствующим обработчикам.
    """
    service = ImportExportService()
    file_path = tmp_path / "service_import.xlsx"
    payload = {
        "groups": [{"id": 1, "name": "IU7-11"}],
    }

    exported_path = service.export_to_xlsx(payload, file_path)
    imported = service.import_from_xlsx(file_path)

    assert exported_path == file_path
    assert imported["groups"][0]["name"] == "IU7-11"


def test_io_tools_emit_basic_logs(tmp_path, caplog):
    """
    Слой io_tools пишет базовые служебные логи при экспорте и импорте.
    """
    service = ImportExportService()
    file_path = tmp_path / "logged_io.xlsx"
    payload = {
        "groups": [{"id": 1, "name": "IU7-11"}],
    }

    with caplog.at_level(logging.DEBUG):
        service.export_to_xlsx(payload, file_path)
        service.import_from_xlsx(file_path)

    assert "XLSX export requested" in caplog.text
    assert "XlsxExporter export started" in caplog.text
    assert "XlsxExporter export finished" in caplog.text
    assert "XLSX import requested" in caplog.text
    assert "XlsxImporter import started" in caplog.text
    assert "XlsxImporter import finished" in caplog.text


def test_xlsx_round_trip_exports_all_database_entities(db_session):
    """
    Проверяет полный круг экспорта данных из БД в XLSX и чтения файла обратно.

    Тест создает по три записи каждой сущности, сохраняет экспорт в папку `logs`,
    затем считывает этот файл через импортёр и сравнивает содержимое всех листов
    с теми данными, которые реально были записаны в базу до экспорта.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.
    :return: `None`. Тест падает, если хотя бы один лист экспортирован или прочитан
        обратно с потерей данных либо нарушением структуры.
    """
    base_time = datetime(2026, 5, 10, 20, 0, 0)

    groups = [
        Group(
            name=f"IU7-9{index}",
            speciality=f"09.03.0{index + 1}_Informatics",
            created_at=base_time.replace(minute=index),
            updated_at=base_time.replace(minute=index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(groups)
    db_session.flush()

    schedules = [
        Schedule(
            odd_or_even="odd" if index % 2 else "even",
            type=f"type_{index}",
            is_assessment=index % 2 == 0,
            day=f"day_{index}",
            time=time(8 + index, 15),
            created_at=base_time.replace(minute=10 + index),
            updated_at=base_time.replace(minute=10 + index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(schedules)
    db_session.flush()

    students = [
        Student(
            group_id=groups[index - 1].id,
            surname=f"Surname{index}",
            first_name=f"Name{index}",
            patronymic=f"Patronymic{index}",
            personal_data=f"PD{index:03d}",
            bmstu_email=f"student{index}@bmstu.ru",
            created_at=base_time.replace(minute=20 + index),
            updated_at=base_time.replace(minute=20 + index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(students)
    db_session.flush()

    schedule_group_links = [
        ScheduleGroupLink(
            group_id=groups[index - 1].id,
            schedule_id=schedules[index - 1].id,
            created_at=base_time.replace(minute=30 + index),
            updated_at=base_time.replace(minute=30 + index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(schedule_group_links)
    db_session.flush()

    lessons = [
        Lesson(
            schedule_id=schedules[index - 1].id,
            topic=f"Topic {index}",
            date=date(2026, 5, 10 + index),
            created_at=base_time.replace(minute=40 + index),
            updated_at=base_time.replace(minute=40 + index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(lessons)
    db_session.flush()

    attendances = [
        Attendance(
            student_id=students[index - 1].id,
            lesson_id=lessons[index - 1].id,
            is_visited=index % 2 == 1,
            created_at=base_time.replace(minute=50 + index),
            updated_at=base_time.replace(minute=50 + index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(attendances)
    db_session.flush()

    marks = [
        Mark(
            student_id=students[index - 1].id,
            lesson_id=lessons[index - 1].id,
            data=2 + index,
            created_at=base_time.replace(hour=21, minute=index),
            updated_at=base_time.replace(hour=21, minute=index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(marks)
    db_session.flush()

    comments = [
        Comment(
            student_id=students[index - 1].id,
            lesson_id=lessons[index - 1].id,
            data=f"Comment {index}",
            created_at=base_time.replace(hour=21, minute=10 + index),
            updated_at=base_time.replace(hour=21, minute=10 + index, second=10),
        )
        for index in range(1, 4)
    ]
    db_session.add_all(comments)
    db_session.flush()

    expected_rows = {
        "groups": [_normalize_db_row(row, "groups") for row in groups],
        "schedules": [_normalize_db_row(row, "schedules") for row in schedules],
        "students": [_normalize_db_row(row, "students") for row in students],
        "schedule_group_links": [
            _normalize_db_row(row, "schedule_group_links")
            for row in schedule_group_links
        ],
        "lessons": [_normalize_db_row(row, "lessons") for row in lessons],
        "attendances": [_normalize_db_row(row, "attendances") for row in attendances],
        "marks": [_normalize_db_row(row, "marks") for row in marks],
        "comments": [_normalize_db_row(row, "comments") for row in comments],
    }

    logs_dir = _logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_path = logs_dir / "test_io_tools_round_trip.xlsx"

    orm_service = OrmService(db_session, auto_commit=False)
    importer = ImportExportService()
    exported_path = orm_service.export_to_xlsx(
        [sheet_name[:-1] if sheet_name.endswith("s") else sheet_name for sheet_name in XLSX_SHEETS_ORDER],
        file_path,
    )
    imported_rows = importer.import_from_xlsx(exported_path)

    assert exported_path == file_path
    assert tuple(imported_rows) == XLSX_SHEETS_ORDER

    for sheet_name in XLSX_SHEETS_ORDER:
        assert _normalize_imported_rows(
            imported_rows[sheet_name],
            expected_rows[sheet_name],
        ) == _sorted_rows(
            expected_rows[sheet_name]
        )
