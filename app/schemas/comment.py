"""
Модуль схем для сущности Comment.
"""
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_empty_string,
    validate_not_none_fields,
)


class CommentBaseSchema(AppBaseSchema):
    """
    Базовая схема комментария.
    """

    student_id: int | None = None
    lesson_id: int | None = None
    data: str | None = Field(default=None, max_length=4096)

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
    data: str = Field(..., min_length=1, max_length=4096)


class CommentFilterSchema(CommentBaseSchema):
    """
    Схема для фильтрации комментариев.
    """


class CommentUpdateSchema(CommentBaseSchema):
    """
    Схема для обновления комментария.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("student_id", "lesson_id", "data"))
        return validated


class CommentDeleteSchema(CommentBaseSchema):
    """
    Схема для удаления комментариев по фильтру.
    """

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

    student_id: int
    lesson_id: int
    data: str
