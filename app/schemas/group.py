"""
Модуль схем для сущности Group.

Файл содержит схемы, используемые при работе с моделью Group:
- базовую схему с общими полями;
- схему создания;
- схему фильтрации;
- схему обновления;
- схему удаления;
- схему чтения данных.

Файл также содержит функции мягкой проверки формата полей `name`
и `speciality`. Эти проверки не блокируют операции сервиса.
Пустая строка `""` в строковых полях схем не допускается.
"""
import re
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.group import MAX_LEN
from app.schemas.base import AppBaseSchema, BaseReadSchema


GROUP_NAME_PATTERN = r"^([А-Я]{1,3})\d{1,2}-\d{1,2}[А-Я]?$"
SPECIALITY_PATTERN = r"^\d{2}\.\d{2}\.\d{2}_.+$"
DEPARTMENTS = frozenset({"ФН", "Э", "СМ", "РЛ", "ИУ", "БМТ", "МТ", "АК", "ПС"})


def is_group_name_formatted(value: str) -> bool:
    """
    Выполняет мягкую проверку формата поля `name`.

    Функция возвращает `True`, если значение соответствует шаблону названия
    группы и содержит допустимое обозначение факультета или кафедры.
    """
    match = re.fullmatch(GROUP_NAME_PATTERN, value)
    if match is None:
        return False

    return match.group(1) in DEPARTMENTS


def is_speciality_formatted(value: str) -> bool:
    """
    Выполняет мягкую проверку формата поля `speciality`.

    Функция возвращает `True`, если значение соответствует шаблону записи
    специальности.
    """
    return re.fullmatch(SPECIALITY_PATTERN, value) is not None


class GroupBaseSchema(AppBaseSchema):
    """
    Базовая схема группы.

    Класс задает поля:
    - `name`;
    - `speciality`.

    Пустая строка в строковых полях не допускается.
    Формат значений в этой схеме жестко не проверяется.
    Остальные схемы Group наследуются от этого класса.
    """

    name: str | None = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])

    @field_validator("name", "speciality")
    @classmethod
    def validate_not_empty_string(cls, value: str | None) -> str | None:
        """
        Запрещает пустую строку в строковых полях схемы.

        Значение `None` допускается только для опциональных полей.
        """
        if value == "":
            raise ValueError("Пустая строка не допускается.")

        return value


class GroupCreateSchema(GroupBaseSchema):
    """
    Схема для создания группы.

    Поле `name` обязательно и не должно быть пустым.
    """

    name: str = Field(..., min_length=1, max_length=MAX_LEN["name"])


class GroupFilterSchema(GroupBaseSchema):
    """
    Схема для фильтрации групп.

    Пустой словарь допустим.
    Пустой фильтр означает выборку всех групп.
    Формат значений в фильтре не ограничивается.
    Пустая строка в полях не допускается.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет исходные данные фильтра до валидации полей.

        Пустой фильтр допустим.
        Метод не ограничивает формат полей `name` и `speciality`.
        Проверка пустой строки выполняется на уровне полей схемы.
        """
        return data


class GroupUpdateSchema(GroupBaseSchema):
    """
    Схема для обновления группы.

    Для обновления требуется непустой набор полей.
    Поле `name`, если передано, не должно быть равно `None`.
    Пустая строка в полях не допускается.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет исходные данные обновления до валидации полей.

        Для обновления требуется непустой словарь.
        Поле `name`, если передано, не должно быть равно `None`.
        Проверка пустой строки выполняется на уровне полей схемы.
        """
        if not isinstance(data, dict) or not data:
            raise ValueError("Для обновления нужно передать хотя бы одно поле.")

        if "name" in data and data["name"] is None:
            raise ValueError("Поле name не может быть None.")

        return data


class GroupDeleteSchema(GroupBaseSchema):
    """
    Схема для удаления групп по фильтру.

    Для удаления требуется непустой фильтр.
    Формат значений в фильтре не ограничивается.
    Пустая строка в полях не допускается.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет исходные данные удаления до валидации полей.

        Для удаления требуется непустой словарь.
        Метод не ограничивает формат полей `name` и `speciality`.
        Проверка пустой строки выполняется на уровне полей схемы.
        """
        if not isinstance(data, dict) or not data:
            raise ValueError("Фильтр удаления не должен быть пустым.")

        return data


class GroupReadSchema(BaseReadSchema):
    """
    Схема чтения данных группы.

    Класс описывает данные, возвращаемые при чтении объекта Group.
    """

    name: str
    speciality: str | None = None
