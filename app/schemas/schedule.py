"""
Модуль схем для сущности Schedule.
"""
from datetime import datetime
from datetime import time as time_type
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.schedule import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    strip_service_fields,
    validate_non_empty_mapping,
    validate_not_empty_string,
)


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

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return strip_service_fields(data)


class ScheduleFilterSchema(ScheduleBaseSchema):
    """
    Схема для фильтрации расписаний.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    odd_or_even: str | None = Field(default=None, max_length=MAX_LEN["odd_or_even"])
    type: str | None = Field(default=None, max_length=MAX_LEN["type"])
    is_assessment: bool | None = None
    day: str | None = Field(default=None, max_length=MAX_LEN["day"])
    time: time_type | None = None


class ScheduleUpdateSchema(ScheduleBaseSchema):
    """
    Схема для обновления расписания.
    """

    odd_or_even: str | None = Field(default=None, max_length=MAX_LEN["odd_or_even"])
    type: str | None = Field(default=None, max_length=MAX_LEN["type"])
    is_assessment: bool | None = None
    day: str | None = Field(default=None, max_length=MAX_LEN["day"])
    time: time_type | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class ScheduleDeleteSchema(ScheduleBaseSchema):
    """
    Схема для удаления расписаний по фильтру.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    odd_or_even: str | None = Field(default=None, max_length=MAX_LEN["odd_or_even"])
    type: str | None = Field(default=None, max_length=MAX_LEN["type"])
    is_assessment: bool | None = None
    day: str | None = Field(default=None, max_length=MAX_LEN["day"])
    time: time_type | None = None

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

    pass
