"""
Модуль схем для сущности Schedule.
"""
from datetime import time as time_type
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.schedule import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_empty_string,
)


def validate_schedule_update_data(data: Any) -> Any:
    """
    Проверяет, что обновление содержит id и хотя бы одно изменяемое поле.
    """
    validated = validate_non_empty_mapping(
        data,
        "Для обновления нужно передать id и хотя бы одно изменяемое поле.",
    )
    if "id" not in validated:
        raise ValueError("Для обновления нужно передать id.")

    if len(validated) == 1:
        raise ValueError("Для обновления нужно передать хотя бы одно изменяемое поле.")

    return validated


def validate_schedule_delete_filter(data: Any) -> Any:
    """
    Проверяет фильтр удаления расписания.
    """
    validated = validate_non_empty_mapping(
        data,
        "Фильтр удаления не должен быть пустым.",
    )
    if set(validated) == {"is_assessment"}:
        raise ValueError("Нельзя удалять расписания только по is_assessment.")

    return validated


class ScheduleBaseSchema(AppBaseSchema):
    """
    Базовая схема расписания.
    """

    odd_or_even: str | None = Field(default=None, max_length=MAX_LEN["odd_or_even"])
    type: str | None = Field(default=None, max_length=MAX_LEN["type"])
    is_assessment: bool | None = None
    day: str | None = Field(default=None, max_length=MAX_LEN["day"])
    time: time_type | None = None

    @field_validator("odd_or_even", "type", "day")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        return validate_not_empty_string(value)


class ScheduleCreateSchema(ScheduleBaseSchema):
    """
    Схема для создания расписания.
    """

    odd_or_even: str = Field(..., min_length=1, max_length=MAX_LEN["odd_or_even"])
    type: str = Field(..., min_length=1, max_length=MAX_LEN["type"])
    is_assessment: bool = False
    day: str = Field(..., min_length=1, max_length=MAX_LEN["day"])
    time: time_type


class ScheduleFilterSchema(ScheduleBaseSchema):
    """
    Схема для фильтрации расписаний.
    """

    id: int = None
    odd_or_even: str = Field(default=None, max_length=MAX_LEN["odd_or_even"])
    type: str = Field(default=None, max_length=MAX_LEN["type"])
    is_assessment: bool = None
    day: str = Field(default=None, max_length=MAX_LEN["day"])
    time: time_type = None


class ScheduleUpdateSchema(ScheduleBaseSchema):
    """
    Схема для обновления расписания.
    """

    id: int
    odd_or_even: str = Field(default=None, max_length=MAX_LEN["odd_or_even"])
    type: str = Field(default=None, max_length=MAX_LEN["type"])
    is_assessment: bool = None
    day: str = Field(default=None, max_length=MAX_LEN["day"])
    time: time_type = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_schedule_update_data(data)


class ScheduleDeleteSchema(ScheduleBaseSchema):
    """
    Схема для удаления расписаний по фильтру.
    """

    id: int = None
    odd_or_even: str = Field(default=None, max_length=MAX_LEN["odd_or_even"])
    type: str = Field(default=None, max_length=MAX_LEN["type"])
    is_assessment: bool = None
    day: str = Field(default=None, max_length=MAX_LEN["day"])
    time: time_type = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_schedule_delete_filter(data)


class ScheduleReadSchema(BaseReadSchema):
    """
    Схема чтения данных расписания.
    """

    odd_or_even: str
    type: str
    is_assessment: bool
    day: str
    time: time_type
