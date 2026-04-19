"""
Модуль схем для сущности Schedule.
"""
from datetime import time as time_type
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_empty_string,
    validate_not_none_fields,
)


class ScheduleBaseSchema(AppBaseSchema):
    """
    Базовая схема расписания.
    """

    odd_or_even: str | None = Field(default=None, max_length=16)
    type: str | None = Field(default=None, max_length=64)
    is_assessment: bool | None = None
    day: str | None = Field(default=None, max_length=16)
    time: time_type | None = None

    @field_validator("odd_or_even", "type", "day")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        return validate_not_empty_string(value)


class ScheduleCreateSchema(ScheduleBaseSchema):
    """
    Схема для создания расписания.
    """

    odd_or_even: str = Field(..., min_length=1, max_length=16)
    type: str = Field(..., min_length=1, max_length=64)
    day: str = Field(..., min_length=1, max_length=16)
    time: time_type
    is_assessment: bool = False


class ScheduleFilterSchema(ScheduleBaseSchema):
    """
    Схема для фильтрации расписаний.
    """


class ScheduleUpdateSchema(ScheduleBaseSchema):
    """
    Схема для обновления расписания.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("odd_or_even", "type", "day", "time"))
        return validated


class ScheduleDeleteSchema(ScheduleBaseSchema):
    """
    Схема для удаления расписаний по фильтру.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class ScheduleReadSchema(BaseReadSchema):
    """
    Схема чтения данных расписания.
    """

    odd_or_even: str
    type: str
    is_assessment: bool
    day: str
    time: time_type
