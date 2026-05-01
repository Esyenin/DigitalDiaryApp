"""
Модуль схем для сущности Attendance.
"""
from datetime import datetime
from typing import Any

from pydantic import model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    strip_service_fields,
    validate_non_empty_mapping,
)


class AttendanceBaseSchema(AppBaseSchema):
    """
    Базовая схема посещаемости.
    """

    student_id: int | None = None
    lesson_id: int | None = None
    is_visited: bool | None = None


class AttendanceCreateSchema(AttendanceBaseSchema):
    """
    Схема для создания посещаемости.
    """

    student_id: int
    lesson_id: int
    is_visited: bool = False

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return strip_service_fields(data)


class AttendanceFilterSchema(AttendanceBaseSchema):
    """
    Схема для фильтрации посещаемости.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    is_visited: bool | None = None


class AttendanceUpdateSchema(AppBaseSchema):
    """
    Схема для обновления посещаемости.
    """

    is_visited: bool

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class AttendanceDeleteSchema(AttendanceBaseSchema):
    """
    Схема для удаления посещаемости по фильтру.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    is_visited: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class AttendanceReadSchema(BaseReadSchema):
    """
    Схема чтения данных посещаемости.
    """

    pass
