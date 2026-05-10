"""
Схемы Pydantic для сущности занятия.
"""
from datetime import date as date_type
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.lesson import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    strip_service_fields,
    validate_non_empty_mapping,
    validate_not_empty_string,
)


class LessonBaseSchema(AppBaseSchema):
    """
    Базовая схема занятия.

    Содержит ссылку на запись расписания и данные, описывающие конкретное
    проведенное занятие.
    """

    schedule_id: int | None = None
    topic: str | None = Field(default=None, max_length=MAX_LEN["topic"])
    date: date_type | None = None

    @field_validator("topic")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        """
        Проверяет поле темы занятия на недопустимую пустую строку.

        :param value: Значение поля `topic`.
        :return: Исходное значение, если оно допустимо.
        """
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
        """
        Убирает из входных данных служебные поля перед созданием занятия.

        :param data: Невалидированные входные данные.
        :return: Данные без служебных полей.
        """
        return strip_service_fields(data)


class LessonFilterSchema(LessonBaseSchema):
    """
    Схема фильтрации занятий.
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
        """
        Проверяет, что в обновлении есть хотя бы одно поле.

        :param data: Невалидированные входные данные.
        :return: Очищенный словарь обновляемых полей.
        :raises ValueError: Если обновлять нечего.
        """
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class LessonDeleteSchema(LessonBaseSchema):
    """
    Схема фильтра для удаления занятий.
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
        """
        Проверяет, что удаление выполняется по непустому фильтру.

        :param data: Невалидированные входные данные.
        :return: Проверенный фильтр удаления.
        :raises ValueError: Если фильтр удаления пустой.
        """
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )
