"""
Модуль схем для сущности Comment.
"""
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.comment import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    strip_service_fields,
    validate_non_empty_mapping,
    validate_not_empty_string,
)


class CommentBaseSchema(AppBaseSchema):
    """
    Базовая схема комментария.
    """

    student_id: int | None = None
    lesson_id: int | None = None
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @field_validator("data")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        return validate_not_empty_string(value)


class CommentCreateSchema(CommentBaseSchema):
    """
    Схема для создания комментария.
    """

    student_id: int
    lesson_id: int
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return strip_service_fields(data)


class CommentFilterSchema(CommentBaseSchema):
    """
    Схема для фильтрации комментариев.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])


class CommentUpdateSchema(AppBaseSchema):
    """
    Схема для обновления комментария.
    """

    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @field_validator("data")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        return validate_not_empty_string(value)

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class CommentDeleteSchema(CommentBaseSchema):
    """
    Схема для удаления комментариев по фильтру.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class CommentReadSchema(BaseReadSchema):
    """
    Схема чтения данных комментария.
    """

    pass
