"""
Модуль схем для сущности Comment.
"""
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.comment import MAX_LEN
from app.schemas.base import AppBaseSchema, BaseReadSchema, validate_not_empty_string


def validate_comment_key(data: dict[str, object]) -> None:
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


def validate_comment_delete_filter(data: Any) -> Any:
    """
    Проверяет, что фильтр удаления содержит id, student_id или lesson_id.
    """
    if not isinstance(data, dict) or not data:
        raise ValueError("Фильтр удаления не должен быть пустым.")

    if not any(field_name in data for field_name in ("id", "student_id", "lesson_id")):
        raise ValueError("Для удаления нужно передать id, student_id или lesson_id.")

    return data


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


class CommentFilterSchema(CommentBaseSchema):
    """
    Схема для фильтрации комментариев.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    data: str = Field(default=None, max_length=MAX_LEN["data"])


class CommentUpdateSchema(CommentBaseSchema):
    """
    Схема для обновления комментария.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    data: str = Field(..., min_length=1, max_length=MAX_LEN["data"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("Данные обновления должны быть словарем.")

        validate_comment_key(data)
        return data


class CommentDeleteSchema(CommentBaseSchema):
    """
    Схема для удаления комментариев по фильтру.
    """

    id: int = None
    student_id: int = None
    lesson_id: int = None
    data: str = Field(default=None, max_length=MAX_LEN["data"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_comment_delete_filter(data)


class CommentReadSchema(BaseReadSchema):
    """
    Схема чтения данных комментария.
    """

    student_id: int
    lesson_id: int
    data: str | None = None
