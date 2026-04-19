"""
Модуль базовых Pydantic-схем.
"""
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict


class AppBaseSchema(BaseModel):
    """
    Базовая схема проекта.
    """

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class IdSchema(AppBaseSchema):
    """
    Схема с полем идентификатора записи.
    """

    id: int


class TimestampSchema(AppBaseSchema):
    """
    Схема с полями времени создания и обновления записи.
    """

    created_at: datetime
    updated_at: datetime


class BaseReadSchema(IdSchema, TimestampSchema):
    """
    Базовая схема чтения данных из БД.
    """


def validate_not_empty_string(value: str | None) -> str | None:
    """
    Запрещает пустую строку в строковых полях схем.
    """
    if value == "":
        raise ValueError("Пустая строка не допускается.")

    return value


def validate_non_empty_mapping(data: Any, message: str) -> Any:
    """
    Проверяет, что данные представлены непустым словарем.
    """
    if not isinstance(data, Mapping) or not data:
        raise ValueError(message)

    return data


def validate_not_none_fields(
    data: Mapping[str, object],
    field_names: Iterable[str],
) -> None:
    """
    Проверяет, что перечисленные поля, если переданы, не равны None.
    """
    for field_name in field_names:
        if field_name in data and data[field_name] is None:
            raise ValueError(f"Поле {field_name} не может быть None.")
