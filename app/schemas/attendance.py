"""
Модуль схем для сущности Attendance.
"""
from typing import Any

from pydantic import model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_none_fields,
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


class AttendanceFilterSchema(AttendanceBaseSchema):
    """
    Схема для фильтрации посещаемости.
    """


class AttendanceUpdateSchema(AttendanceBaseSchema):
    """
    Схема для обновления посещаемости.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("student_id", "lesson_id", "is_visited"))
        return validated


class AttendanceDeleteSchema(AttendanceBaseSchema):
    """
    Схема для удаления посещаемости по фильтру.
    """

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

    student_id: int
    lesson_id: int
    is_visited: bool
