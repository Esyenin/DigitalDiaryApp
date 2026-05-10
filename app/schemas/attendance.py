"""
Схемы Pydantic для сущности посещаемости.
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


class AttendanceBaseSchema(AppBaseSchema):
    """
    Базовая схема посещаемости.

    Описывает поля записи, связывающей студента с конкретным занятием.
    """

    student_id: int | None = None
    lesson_id: int | None = None
    is_visited: bool | None = None


class AttendanceCreateSchema(AttendanceBaseSchema):
    """
    Схема для создания записи посещаемости.
    """

    student_id: int
    lesson_id: int
    is_visited: bool = False

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Убирает из входных данных служебные поля перед созданием записи.

        :param data: Невалидированные входные данные.
        :return: Данные без служебных полей.
        """
        return strip_service_fields(data)


class AttendanceFilterSchema(AttendanceBaseSchema):
    """
    Схема фильтрации записей посещаемости.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    is_visited: bool | None = None


class AttendanceUpdateSchema(AppBaseSchema):
    """
    Схема для обновления посещаемости.

    Разрешает менять только значение факта посещения. Привязка к студенту и
    занятию определяется не этой схемой, а фильтром или объектом записи.
    """

    is_visited: bool

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


class AttendanceDeleteSchema(AttendanceBaseSchema):
    """
    Схема фильтра для удаления записей посещаемости.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    is_visited: bool | None = None

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


class AttendanceReadSchema(BaseReadSchema):
    """
    Заглушка для схемы чтения посещаемости.
    """

    pass
