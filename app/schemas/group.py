"""
Схемы Pydantic для сущности учебной группы.
"""
import re
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.group import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    strip_service_fields,
    validate_non_empty_mapping,
    validate_not_empty_string,
    validate_not_none_fields,
)


GROUP_NAME_PATTERN = r"^([А-Я]{1,3})\d{1,2}-\d{1,2}[А-Я]?$"
SPECIALITY_PATTERN = r"^\d{2}\.\d{2}\.\d{2}_.+$"
DEPARTMENTS = frozenset({"ФН", "Э", "СМ", "РЛ", "ИУ", "БМТ", "МТ", "АК", "ПС"})


def is_group_name_formatted(value: str) -> bool:
    """
    Проверяет, соответствует ли имя группы ожидаемому шаблону.

    Функция используется как вспомогательная проверка формата и не выбрасывает
    исключение: она только сообщает, подходит значение под шаблон или нет.

    :param value: Проверяемое имя группы.
    :return: `True`, если имя соответствует шаблону, иначе `False`.
    """
    match = re.fullmatch(GROUP_NAME_PATTERN, value)
    if match is None:
        return False

    return match.group(1) in DEPARTMENTS


def is_speciality_formatted(value: str) -> bool:
    """
    Проверяет, соответствует ли строка специальности ожидаемому формату.

    :param value: Проверяемое значение специальности.
    :return: `True`, если значение соответствует шаблону, иначе `False`.
    """
    return re.fullmatch(SPECIALITY_PATTERN, value) is not None


class GroupBaseSchema(AppBaseSchema):
    """
    Базовая схема группы.

    Описывает все изменяемые пользовательские поля сущности `Group`.
    """

    name: str | None = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])

    @field_validator("name", "speciality")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        """
        Проверяет строковые поля группы на недопустимую пустую строку.

        :param value: Значение поля `name` или `speciality`.
        :return: Исходное значение, если оно допустимо.
        """
        return validate_not_empty_string(value)


class GroupCreateSchema(GroupBaseSchema):
    """
    Схема для создания группы.

    Требует только те поля, без которых запись группы не может быть создана.
    """

    name: str = Field(..., min_length=1, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Убирает из входных данных служебные поля перед созданием группы.

        :param data: Невалидированные входные данные.
        :return: Данные без служебных полей.
        """
        return strip_service_fields(data)


class GroupFilterSchema(GroupBaseSchema):
    """
    Схема фильтрации групп.

    Разрешает указывать любые поля сущности и служебные поля для построения
    условий поиска.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    name: str | None = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет корректность сырых данных фильтра группы.

        :param data: Невалидированные входные данные.
        :return: Исходные данные, если они допустимы для фильтрации.
        """
        if isinstance(data, dict):
            validate_not_none_fields(data, ("id", "name"))

        return data


class GroupUpdateSchema(GroupBaseSchema):
    """
    Схема для обновления группы.

    Принимает только поля, значения которых действительно могут быть изменены.
    """

    name: str | None = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Подготавливает и проверяет данные для частичного обновления группы.

        :param data: Невалидированные входные данные.
        :return: Очищенный словарь обновляемых полей.
        :raises ValueError: Если после очистки не осталось ни одного поля для
            обновления или если обязательное по смыслу поле явно равно `None`.
        """
        cleaned = strip_service_fields(data)
        validated = validate_non_empty_mapping(
            cleaned,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("name",))
        return validated


class GroupDeleteSchema(GroupBaseSchema):
    """
    Схема фильтра для удаления групп.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    name: str | None = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет, что удаление группы выполняется по непустому фильтру.

        :param data: Невалидированные входные данные.
        :return: Проверенный фильтр удаления.
        :raises ValueError: Если фильтр пуст или содержит недопустимое
            значение `None` в чувствительных полях.
        """
        validated = validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )
        validate_not_none_fields(validated, ("id", "name"))
        return validated
