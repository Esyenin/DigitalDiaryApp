"""
Модуль схем для сущности Mark.
"""
from typing import Any

from pydantic import model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_none_fields,
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


class MarkFilterSchema(MarkBaseSchema):
    """
    Схема для фильтрации оценок.
    """


class MarkUpdateSchema(MarkBaseSchema):
    """
    Схема для обновления оценки.
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


class MarkDeleteSchema(MarkBaseSchema):
    """
    Схема для удаления оценок по фильтру.
    """

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

    student_id: int
    lesson_id: int
    data: int
