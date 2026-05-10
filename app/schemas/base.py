"""
Базовые схемы и общие функции валидации для слоя `app.schemas`.
"""
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict


class AppBaseSchema(BaseModel):
    """
    Общая базовая схема проекта.

    Содержит единые настройки Pydantic, которые применяются ко всем
    прикладным схемам проекта.
    """

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class IdSchema(AppBaseSchema):
    """
    Схема с идентификатором записи.
    """

    id: int


class TimestampSchema(AppBaseSchema):
    """
    Схема со служебными полями времени создания и обновления записи.
    """

    created_at: datetime
    updated_at: datetime


class BaseReadSchema(IdSchema, TimestampSchema):
    """
    Базовая схема чтения данных из базы данных.

    Используется как заглушка для read-схем, когда отдельная структура
    ответа для сущности пока не требуется.
    """


SERVICE_FIELD_NAMES = frozenset({"id", "created_at", "updated_at"})


def strip_service_fields(
    data: Any,
    field_names: Iterable[str] = SERVICE_FIELD_NAMES,
) -> Any:
    """
    Удаляет из входных данных служебные поля модели.

    :param data: Произвольные входные данные, которые потенциально содержат
        служебные поля.
    :param field_names: Имена полей, которые не должны приниматься схемой как
        пользовательские данные.
    :return: Исходный объект без изменений, если это не отображение, либо
        новый словарь без служебных полей.
    """
    if not isinstance(data, Mapping):
        return data

    ignored_fields = frozenset(field_names)
    return {
        key: value
        for key, value in data.items()
        if key not in ignored_fields
    }


def validate_not_empty_string(
        value: str | None
) -> str | None:
    """
    Проверяет, что строковое значение не является пустой строкой.

    :param value: Значение строкового поля схемы.
    :return: Исходное значение, если оно допустимо.
    :raises ValueError: Если передана пустая строка.
    """
    if value == "":
        raise ValueError("Пустая строка не допускается.")

    return value


def validate_non_empty_mapping(
        data: Any,
        message: str
) -> Any:
    """
    Проверяет, что входные данные представлены непустым отображением.

    :param data: Данные, переданные в схему до валидации Pydantic.
    :param message: Текст ошибки, который нужно вернуть при невалидных данных.
    :return: Исходные данные, если они представлены непустым отображением.
    :raises ValueError: Если данные не являются отображением или оно пустое.
    """
    if not isinstance(data, Mapping) or not data:
        raise ValueError(message)

    return data


def validate_not_none_fields(
    data: Mapping[str, object],
    field_names: Iterable[str],
) -> None:
    """
    Проверяет, что указанные поля, если они присутствуют во входных данных,
    не содержат значение `None`.

    :param data: Словарь данных, прошедший предварительную нормализацию.
    :param field_names: Имена полей, для которых значение `None`
        недопустимо.
    :raises ValueError: Если хотя бы одно из перечисленных полей явно равно
        `None`.
    """
    for field_name in field_names:
        if field_name in data and data[field_name] is None:
            raise ValueError(f"Поле {field_name} не может быть None.")
