"""
Модуль схем для сущности Student.
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


class StudentBaseSchema(AppBaseSchema):
    """
    Базовая схема студента.
    """

    group_id: int | None = None
    surname: str | None = Field(default=None, max_length=128)
    first_name: str | None = Field(default=None, max_length=128)
    patronymic: str | None = Field(default=None, max_length=128)
    personal_data: str | None = Field(default=None, max_length=16)
    bmstu_email: str | None = Field(default=None, max_length=128)

    @field_validator(
        "surname",
        "first_name",
        "patronymic",
        "personal_data",
        "bmstu_email",
    )
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        return validate_not_empty_string(value)


class StudentCreateSchema(StudentBaseSchema):
    """
    Схема для создания студента.
    """

    group_id: int
    surname: str = Field(..., min_length=1, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=128)


class StudentFilterSchema(StudentBaseSchema):
    """
    Схема для фильтрации студентов.
    """


class StudentUpdateSchema(StudentBaseSchema):
    """
    Схема для обновления студента.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("group_id", "surname", "first_name"))
        return validated


class StudentDeleteSchema(StudentBaseSchema):
    """
    Схема для удаления студентов по фильтру.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class StudentReadSchema(BaseReadSchema):
    """
    Схема чтения данных студента.
    """

    group_id: int
    surname: str
    first_name: str
    patronymic: str | None = None
    personal_data: str | None = None
    bmstu_email: str | None = None
