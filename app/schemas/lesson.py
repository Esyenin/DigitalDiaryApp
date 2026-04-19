"""
Модуль схем для сущности Lesson.
"""
from datetime import date as date_type
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_empty_string,
    validate_not_none_fields,
)


class LessonBaseSchema(AppBaseSchema):
    """
    Базовая схема занятия.
    """

    schedule_id: int | None = None
    topic: str | None = Field(default=None, max_length=512)
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
    date: date_type


class LessonFilterSchema(LessonBaseSchema):
    """
    Схема для фильтрации занятий.
    """


class LessonUpdateSchema(LessonBaseSchema):
    """
    Схема для обновления занятия.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("schedule_id", "date"))
        return validated


class LessonDeleteSchema(LessonBaseSchema):
    """
    Схема для удаления занятий по фильтру.
    """

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

    schedule_id: int
    topic: str | None = None
    date: date_type
