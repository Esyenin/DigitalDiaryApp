"""
Модуль схем для сущности Group.
"""
import re
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.group import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_empty_string,
)


GROUP_NAME_PATTERN = r"^([А-Я]{1,3})\d{1,2}-\d{1,2}[А-Я]?$"
SPECIALITY_PATTERN = r"^\d{2}\.\d{2}\.\d{2}_.+$"
DEPARTMENTS = frozenset({"ФН", "Э", "СМ", "РЛ", "ИУ", "БМТ", "МТ", "АК", "ПС"})


def is_group_name_formatted(value: str) -> bool:
    """
    Выполняет мягкую проверку формата поля `name`.
    """
    match = re.fullmatch(GROUP_NAME_PATTERN, value)
    if match is None:
        return False

    return match.group(1) in DEPARTMENTS


def is_speciality_formatted(value: str) -> bool:
    """
    Выполняет мягкую проверку формата поля `speciality`.
    """
    return re.fullmatch(SPECIALITY_PATTERN, value) is not None


class GroupBaseSchema(AppBaseSchema):
    """
    Базовая схема группы.
    """

    name: str | None = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])

    @field_validator("name", "speciality")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        return validate_not_empty_string(value)


class GroupCreateSchema(GroupBaseSchema):
    """
    Схема для создания группы.
    """

    name: str = Field(..., min_length=1, max_length=MAX_LEN["name"])
    speciality: str | None = Field(default=None, max_length=MAX_LEN["speciality"])


class GroupFilterSchema(GroupBaseSchema):
    """
    Схема для фильтрации групп.
    """

    id: int = None
    name: str = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str = Field(default=None, max_length=MAX_LEN["speciality"])


class GroupUpdateSchema(GroupBaseSchema):
    """
    Схема для обновления группы.
    """

    id: int = None
    name: str = Field(default=None, max_length=MAX_LEN["name"])
    speciality: str = Field(default=None, max_length=MAX_LEN["speciality"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        if "id" in validated:
            if len(validated) == 1:
                raise ValueError("Для обновления нужно передать хотя бы одно изменяемое поле.")

            return validated

        if "name" not in validated or "speciality" not in validated:
            raise ValueError("Если id не передан, нужно передать name и speciality.")

        return validated


class GroupDeleteSchema(GroupBaseSchema):
    """
    Схема для удаления групп по фильтру.
    """

    id: int = None
    name: str = Field(default=None, max_length=MAX_LEN["name"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )
        if "id" not in validated and "name" not in validated:
            raise ValueError("Для удаления нужно передать id или name.")

        return validated


class GroupReadSchema(BaseReadSchema):
    """
    Схема чтения данных группы.
    """

    name: str
    speciality: str | None = None
