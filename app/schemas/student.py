"""
Схемы Pydantic для сущности студента.
"""
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.student import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    strip_service_fields,
    validate_non_empty_mapping,
    validate_not_empty_string,
    validate_not_none_fields,
)


class StudentBaseSchema(AppBaseSchema):
    """
    Базовая схема студента.

    Содержит все пользовательские поля, которые могут участвовать
    в создании, фильтрации или обновлении записи студента.
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
        """
        Проверяет строковые поля студента на недопустимую пустую строку.

        :param value: Значение одного из строковых полей студента.
        :return: Исходное значение, если оно допустимо.
        """
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

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Убирает из входных данных служебные поля перед созданием студента.

        :param data: Невалидированные входные данные.
        :return: Данные без служебных полей.
        """
        return strip_service_fields(data)


class StudentFilterSchema(StudentBaseSchema):
    """
    Схема фильтрации студентов.

    Разрешает использовать как пользовательские, так и служебные поля
    сущности в качестве критериев поиска.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group_id: int | None = None
    surname: str | None = Field(default=None, max_length=MAX_LEN["surname"])
    first_name: str | None = Field(default=None, max_length=MAX_LEN["first_name"])
    patronymic: str | None = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str | None = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str | None = Field(default=None, max_length=MAX_LEN["bmstu_email"])


class StudentUpdateSchema(StudentBaseSchema):
    """
    Схема для обновления студента.

    Предназначена только для тех полей, которые могут быть изменены после
    создания записи.
    """

    group_id: int | None = None
    surname: str | None = Field(default=None, max_length=MAX_LEN["surname"])
    first_name: str | None = Field(default=None, max_length=MAX_LEN["first_name"])
    patronymic: str | None = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str | None = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str | None = Field(default=None, max_length=MAX_LEN["bmstu_email"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Подготавливает данные для частичного обновления студента.

        :param data: Невалидированные входные данные.
        :return: Очищенный словарь с изменяемыми полями.
        :raises ValueError: Если обновлять нечего либо критичные поля
            переданы как `None`.
        """
        validated = validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("group_id", "surname", "first_name"))
        return validated


class StudentDeleteSchema(StudentBaseSchema):
    """
    Схема фильтра для удаления студентов.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group_id: int | None = None
    surname: str | None = Field(default=None, max_length=MAX_LEN["surname"])
    first_name: str | None = Field(default=None, max_length=MAX_LEN["first_name"])
    patronymic: str | None = Field(default=None, max_length=MAX_LEN["patronymic"])
    personal_data: str | None = Field(default=None, max_length=MAX_LEN["personal_data"])
    bmstu_email: str | None = Field(default=None, max_length=MAX_LEN["bmstu_email"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет, что удаление студента выполняется по непустому фильтру.

        :param data: Невалидированные входные данные.
        :return: Проверенный фильтр удаления.
        :raises ValueError: Если фильтр удаления пустой.
        """
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class StudentReadSchema(BaseReadSchema):
    """
    Заглушка для схемы чтения студента.
    """

    pass
