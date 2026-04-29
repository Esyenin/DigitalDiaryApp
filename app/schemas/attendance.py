"""
Модуль схем для сущности Attendance.
"""
from typing import Any

from pydantic import model_validator

from app.schemas.base import AppBaseSchema, BaseReadSchema


def validate_attendance_key(data: dict[str, object]) -> None:
    """
    Проверяет, что запись определена id или парой student_id + lesson_id.
    """
    has_id = "id" in data
    has_student_id = "student_id" in data
    has_lesson_id = "lesson_id" in data

    if has_id:
        return

    if has_student_id and has_lesson_id:
        return

    raise ValueError("Нужно передать id или пару student_id и lesson_id.")


def validate_non_empty_filter(data: Any) -> Any:
    """
    Проверяет, что фильтр представлен непустым словарем.
    """
    if not isinstance(data, dict) or not data:
        raise ValueError("Фильтр удаления не должен быть пустым.")

    return data


def validate_attendance_delete_filter(data: Any) -> Any:
    """
    Проверяет, что фильтр удаления содержит идентификатор записи, студента или занятия.
    """
    validated = validate_non_empty_filter(data)
    if not any(field_name in validated for field_name in ("id", "student_id", "lesson_id")):
        raise ValueError("Для удаления нужно передать id, student_id или lesson_id.")

    return validated


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

    id: int = None
    student_id: int = None
    lesson_id: int = None
    is_visited: bool = None


class AttendanceUpdateSchema(AttendanceBaseSchema):
    """
    Схема для обновления посещаемости.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    is_visited: bool

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("Данные обновления должны быть словарем.")

        validate_attendance_key(data)
        return data


class AttendanceDeleteSchema(AttendanceBaseSchema):
    """
    Схема для удаления посещаемости по фильтру.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    is_visited: bool = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_attendance_delete_filter(data)


class AttendanceReadSchema(BaseReadSchema):
    """
    Схема чтения данных посещаемости.
    """

    student_id: int
    lesson_id: int
    is_visited: bool
