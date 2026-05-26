"""
Схемы Pydantic для сущности оценки.
"""
from datetime import datetime
from typing import Any

from pydantic import model_validator

from app.schemas.base import (
    AppBaseSchema,
    strip_service_fields,
    validate_non_empty_mapping,
)


class MarkBaseSchema(AppBaseSchema):
    """
    Базовая схема оценки.

    Описывает балл, выставленный студенту за конкретное занятие.
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
        """
        Убирает из входных данных служебные поля перед созданием оценки.

        :param data: Невалидированные входные данные.
        :return: Данные без служебных полей.
        """
        return strip_service_fields(data)


class MarkFilterSchema(MarkBaseSchema):
    """
    Схема фильтрации оценок.
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

    Позволяет менять только само значение оценки. Привязка к студенту и
    занятию определяется фильтром или ORM-объектом.
    """

    data: int

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет, что в обновление передан непустой набор полей.

        :param data: Невалидированные входные данные.
        :return: Очищенный словарь обновляемых полей.
        :raises ValueError: Если обновлять нечего.
        """
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class MarkDeleteSchema(MarkBaseSchema):
    """
    Схема фильтра для удаления оценок.
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
