"""
Общие схемы и правила сущностей для табличного импорта.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.io_tools.xlsx_config import XLSX_REQUIRED_COLUMNS_BY_SHEET
from app.schemas import (
    AttendanceCreateSchema,
    AttendanceFilterSchema,
    CommentCreateSchema,
    CommentFilterSchema,
    GroupCreateSchema,
    GroupFilterSchema,
    LessonCreateSchema,
    LessonFilterSchema,
    MarkCreateSchema,
    MarkFilterSchema,
    ScheduleCreateSchema,
    ScheduleFilterSchema,
    ScheduleGroupLinkCreateSchema,
    ScheduleGroupLinkFilterSchema,
    StudentCreateSchema,
    StudentFilterSchema,
)


FILTER_SCHEMA_BY_ENTITY: dict[str, type[BaseModel]] = {
    "groups": GroupFilterSchema,
    "schedules": ScheduleFilterSchema,
    "students": StudentFilterSchema,
    "schedule_group_links": ScheduleGroupLinkFilterSchema,
    "lessons": LessonFilterSchema,
    "attendances": AttendanceFilterSchema,
    "marks": MarkFilterSchema,
    "comments": CommentFilterSchema,
}


CREATE_SCHEMA_BY_ENTITY: dict[str, type[BaseModel]] = {
    "groups": GroupCreateSchema,
    "schedules": ScheduleCreateSchema,
    "students": StudentCreateSchema,
    "schedule_group_links": ScheduleGroupLinkCreateSchema,
    "lessons": LessonCreateSchema,
    "attendances": AttendanceCreateSchema,
    "marks": MarkCreateSchema,
    "comments": CommentCreateSchema,
}

STRICT_CREATE_SCHEMA_BY_ENTITY: dict[str, type[BaseModel]] = {
    "groups": GroupCreateSchema,
    "schedules": ScheduleCreateSchema,
    "students": StudentCreateSchema,
    "schedule_group_links": ScheduleGroupLinkCreateSchema,
    "lessons": LessonCreateSchema,
    "attendances": AttendanceCreateSchema,
    "marks": MarkCreateSchema,
    "comments": CommentCreateSchema,
}


def get_known_fields(entity_type: str) -> tuple[str, ...]:
    """
    Возвращает известные поля сущности по filter-схеме.

    :param entity_type: Канонический тип сущности.
    :return: Кортеж известных полей.
    """
    schema = FILTER_SCHEMA_BY_ENTITY.get(entity_type)
    if schema is None:
        return ()

    return tuple(schema.model_fields.keys())


def get_required_fields(entity_type: str) -> tuple[str, ...]:
    """
    Возвращает обязательные поля сущности для табличного импорта.

    :param entity_type: Канонический тип сущности.
    :return: Кортеж обязательных полей.
    """
    return tuple(XLSX_REQUIRED_COLUMNS_BY_SHEET.get(entity_type, ()))
