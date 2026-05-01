"""
Модуль схем для сущности Mark.
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

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return strip_service_fields(data)


class MarkFilterSchema(MarkBaseSchema):
    """
    Схема для фильтрации оценок.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    data: int | None = None


class MarkUpdateSchema(AppBaseSchema):
    """
    Схема для обновления оценки.
    """

    data: int

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class MarkDeleteSchema(MarkBaseSchema):
    """
    Схема для удаления оценок по фильтру.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    data: int | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class MarkReadSchema(BaseReadSchema):
    """
    Схема чтения данных оценки.
    """

    pass
