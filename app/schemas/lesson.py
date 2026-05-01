"""
Модуль схем для сущности Lesson.
"""
from datetime import date as date_type
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.lesson import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    strip_service_fields,
    validate_non_empty_mapping,
    validate_not_empty_string,
)


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

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return strip_service_fields(data)


class LessonFilterSchema(LessonBaseSchema):
    """
    Схема для фильтрации занятий.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schedule_id: int | None = None
    topic: str | None = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type | None = None


class LessonUpdateSchema(LessonBaseSchema):
    """
    Схема для обновления занятия.
    """

    schedule_id: int | None = None
    topic: str | None = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class LessonDeleteSchema(LessonBaseSchema):
    """
    Схема для удаления занятий по фильтру.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schedule_id: int | None = None
    topic: str | None = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class LessonReadSchema(BaseReadSchema):
    """
    Схема чтения данных занятия.
    """

    pass
