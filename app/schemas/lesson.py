"""
Модуль схем для сущности Lesson.
"""
from datetime import date as date_type
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.lesson import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_not_empty_string,
)


def validate_lesson_key(data: dict[str, object]) -> None:
    """
    Проверяет, что занятие определено id или парой schedule_id + date.
    """
    has_id = "id" in data
    has_schedule_id = "schedule_id" in data
    has_date = "date" in data

    if has_id:
        return

    if has_schedule_id and has_date:
        return

    raise ValueError("Нужно передать id или пару schedule_id и date.")


def validate_lesson_delete_filter(data: Any) -> Any:
    """
    Проверяет, что фильтр удаления содержит id или schedule_id.
    """
    if not isinstance(data, dict) or not data:
        raise ValueError("Фильтр удаления не должен быть пустым.")

    if "id" not in data and "schedule_id" not in data:
        raise ValueError("Для удаления нужно передать id или schedule_id.")

    return data


class LessonBaseSchema(AppBaseSchema):
    """
    Базовая схема занятия.
    """

    schedule_id: int | None = None
    topic: str | None = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type | None = None

    @field_validator("topic")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        return validate_not_empty_string(value)


class LessonCreateSchema(LessonBaseSchema):
    """
    Схема для создания занятия.
    """

    schedule_id: int
    topic: str | None = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type


class LessonFilterSchema(LessonBaseSchema):
    """
    Схема для фильтрации занятий.
    """

    id: int = None
    schedule_id: int = None
    topic: str = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type = None


class LessonUpdateSchema(LessonBaseSchema):
    """
    Схема для обновления занятия.
    """

    id: int = None
    schedule_id: int = None
    topic: str | None = Field(..., max_length=MAX_LEN["topic"])
    date: date_type = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("Данные обновления должны быть словарем.")

        validate_lesson_key(data)
        if "topic" not in data:
            raise ValueError("Для обновления нужно передать topic.")

        return data


class LessonDeleteSchema(LessonBaseSchema):
    """
    Схема для удаления занятий по фильтру.
    """

    id: int = None
    schedule_id: int = None
    topic: str = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_lesson_delete_filter(data)


class LessonReadSchema(BaseReadSchema):
    """
    Схема чтения данных занятия.
    """

    schedule_id: int
    topic: str | None = None
    date: date_type
