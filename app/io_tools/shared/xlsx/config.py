"""
Каноническая XLSX-конфигурация подсистемы `io_tools`.

Этот модуль теперь является единственным источником знаний о:

1. порядке листов стандартной XLSX-книги;
2. поддерживаемых сущностях smart- и strict-импорта;
3. составе колонок по листам;
4. обязательных колонках;
5. сопоставлении model name -> sheet key.

Старый `app.io_tools.xlsx_config` оставлен только как compatibility wrapper.
"""
from __future__ import annotations


XLSX_SHEETS_ORDER = (
    "groups",
    "schedules",
    "students",
    "schedule_group_links",
    "lessons",
    "attendances",
    "marks",
    "comments",
)


SMART_IMPORT_ENTITY_TYPES = (
    "groups",
    "schedules",
    "students",
)


STRICT_IMPORT_ENTITY_TYPES = tuple(
    sheet_name
    for sheet_name in XLSX_SHEETS_ORDER
    if sheet_name not in SMART_IMPORT_ENTITY_TYPES
)


XLSX_COLUMNS_BY_SHEET = {
    "groups": (
        "id",
        "name",
        "speciality",
        "created_at",
        "updated_at",
    ),
    "schedules": (
        "id",
        "odd_or_even",
        "type",
        "is_assessment",
        "day",
        "time",
        "created_at",
        "updated_at",
    ),
    "students": (
        "id",
        "group_id",
        "surname",
        "first_name",
        "patronymic",
        "personal_data",
        "bmstu_email",
        "created_at",
        "updated_at",
    ),
    "schedule_group_links": (
        "id",
        "group_id",
        "schedule_id",
        "created_at",
        "updated_at",
    ),
    "lessons": (
        "id",
        "schedule_id",
        "topic",
        "date",
        "created_at",
        "updated_at",
    ),
    "attendances": (
        "id",
        "student_id",
        "lesson_id",
        "is_visited",
        "created_at",
        "updated_at",
    ),
    "marks": (
        "id",
        "student_id",
        "lesson_id",
        "data",
        "created_at",
        "updated_at",
    ),
    "comments": (
        "id",
        "student_id",
        "lesson_id",
        "data",
        "created_at",
        "updated_at",
    ),
}


XLSX_REQUIRED_COLUMNS_BY_SHEET = {
    "groups": ("name",),
    "schedules": ("odd_or_even", "type", "day", "time"),
    "students": ("group_id", "surname", "first_name"),
    "schedule_group_links": ("group_id", "schedule_id"),
    "lessons": ("schedule_id", "date"),
    "attendances": ("student_id", "lesson_id"),
    "marks": ("student_id", "lesson_id", "data"),
    "comments": ("student_id", "lesson_id"),
}


XLSX_SHEET_KEY_BY_MODEL_NAME = {
    "group": "groups",
    "groups": "groups",
    "schedule": "schedules",
    "schedules": "schedules",
    "student": "students",
    "students": "students",
    "schedule_group_link": "schedule_group_links",
    "schedule_group_links": "schedule_group_links",
    "lesson": "lessons",
    "lessons": "lessons",
    "attendance": "attendances",
    "attendances": "attendances",
    "mark": "marks",
    "marks": "marks",
    "comment": "comments",
    "comments": "comments",
}


def get_known_sheet_names() -> tuple[str, ...]:
    """
    Возвращает листы XLSX в согласованном порядке.
    """
    return XLSX_SHEETS_ORDER


def is_smart_import_entity_type(entity_type: str) -> bool:
    """
    Проверяет, поддерживает ли сущность smart-импорт.
    """
    return entity_type in SMART_IMPORT_ENTITY_TYPES


def is_strict_import_entity_type(entity_type: str) -> bool:
    """
    Проверяет, должна ли сущность импортироваться в strict-режиме.
    """
    return entity_type in STRICT_IMPORT_ENTITY_TYPES


def normalize_sheet_keys(
    model_names: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    """
    Приводит имена моделей и листов к каноническим XLSX-ключам.
    """
    if model_names is None:
        return XLSX_SHEETS_ORDER

    normalized_keys: list[str] = []

    for model_name in model_names:
        canonical_key = XLSX_SHEET_KEY_BY_MODEL_NAME.get(model_name)
        if canonical_key is None:
            raise ValueError(
                f"Unsupported model name for XLSX operations: {model_name}."
            )

        if canonical_key not in normalized_keys:
            normalized_keys.append(canonical_key)

    return tuple(
        sheet_name
        for sheet_name in XLSX_SHEETS_ORDER
        if sheet_name in normalized_keys
    )
