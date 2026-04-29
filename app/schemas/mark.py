"""
Модуль схем для сущности Mark.
"""
from typing import Any

from pydantic import model_validator

from app.schemas.base import AppBaseSchema, BaseReadSchema


def validate_mark_key(data: dict[str, object]) -> None:
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


def validate_mark_delete_filter(data: Any) -> Any:
    """
    Проверяет, что фильтр удаления содержит id, student_id или lesson_id.
    """
    if not isinstance(data, dict) or not data:
        raise ValueError("Фильтр удаления не должен быть пустым.")

    if not any(field_name in data for field_name in ("id", "student_id", "lesson_id")):
        raise ValueError("Для удаления нужно передать id, student_id или lesson_id.")

    return data


class MarkBaseSchema(AppBaseSchema):
    """
    Базовая схема оценки.
    """

    student_id: int | None = None
    lesson_id: int | None = None
    data: int | None = None


class MarkCreateSchema(MarkBaseSchema):
    """
    Схема для создания оценки.
    """

    student_id: int
    lesson_id: int
    data: int


class MarkFilterSchema(MarkBaseSchema):
    """
    Схема для фильтрации оценок.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    data: int = None


class MarkUpdateSchema(MarkBaseSchema):
    """
    Схема для обновления оценки.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    data: int

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("Данные обновления должны быть словарем.")

        validate_mark_key(data)
        return data


class MarkDeleteSchema(MarkBaseSchema):
    """
    Схема для удаления оценок по фильтру.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    data: int = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_mark_delete_filter(data)


class MarkReadSchema(BaseReadSchema):
    """
    Схема чтения данных оценки.
    """

    student_id: int
    lesson_id: int
    data: int
