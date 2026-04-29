"""
Модуль схем для сущности Student.
"""
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.student import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    IdSchema,
    validate_non_empty_mapping,
    validate_not_empty_string,
    validate_not_none_fields,
)


def validate_student_delete_filter(data: Any) -> Any:
    """
    Проверяет, что фильтр удаления содержит id или group_id.
    """
    validated = validate_non_empty_mapping(
        data,
        "Фильтр удаления не должен быть пустым.",
    )
    if "id" not in validated and "group_id" not in validated:
        raise ValueError("Для удаления нужно передать id или group_id.")

    return validated


class StudentBaseSchema(AppBaseSchema):
    """
    Базовая схема студента.
    """

    group_id: int | None = None
    surname: str | None = Field(default=None, max_length=MAX_LEN["surname"])
    first_name: str | None = Field(default=None, max_length=MAX_LEN["first_name"])
    patronymic: str | None = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str | None = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str | None = Field(default=None, max_length=MAX_LEN["bmstu_email"])

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
    surname: str = Field(..., min_length=1, max_length=MAX_LEN["surname"])
    first_name: str = Field(..., min_length=1, max_length=MAX_LEN["first_name"])
    patronymic: str | None = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str | None = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str | None = Field(default=None, max_length=MAX_LEN["bmstu_email"])


class StudentFilterSchema(StudentBaseSchema):
    """
    Схема для фильтрации студентов.
    """

    id: int = None
    group_id: int = None
    surname: str = Field(default=None, max_length=MAX_LEN["surname"])
    first_name: str = Field(default=None, max_length=MAX_LEN["first_name"])
    patronymic: str = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str = Field(default=None, max_length=MAX_LEN["bmstu_email"])


class StudentUpdateSchema(IdSchema, StudentBaseSchema):
    """
    Схема для обновления студента.
    """

    id: int
    group_id: int | None = None
    surname: str | None = Field(default=None, max_length=MAX_LEN["surname"])
    first_name: str | None = Field(default=None, max_length=MAX_LEN["first_name"])
    patronymic: str | None = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str | None = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str | None = Field(default=None, max_length=MAX_LEN["bmstu_email"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        if set(validated) == {"id"}:
            raise ValueError("Для обновления нужно передать хотя бы одно изменяемое поле.")

        validate_not_none_fields(validated, ("group_id", "surname", "first_name"))
        return validated


class StudentDeleteSchema(StudentBaseSchema):
    """
    Схема для удаления студентов по фильтру.
    """

    id: int = None
    group_id: int = None
    surname: str = Field(default=None, max_length=MAX_LEN["surname"])
    first_name: str = Field(default=None, max_length=MAX_LEN["first_name"])
    patronymic: str = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str = Field(default=None, max_length=MAX_LEN["bmstu_email"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_student_delete_filter(data)


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
