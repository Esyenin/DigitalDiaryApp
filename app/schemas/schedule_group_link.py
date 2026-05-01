"""
Модуль схем для сущности ScheduleGroupLink.
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


class ScheduleGroupLinkBaseSchema(AppBaseSchema):
    """
    Базовая схема связи расписания и группы.
    """

    group_id: int | None = None
    schedule_id: int | None = None


class ScheduleGroupLinkCreateSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для создания связи.
    """

    group_id: int
    schedule_id: int

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return strip_service_fields(data)


class ScheduleGroupLinkFilterSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для фильтрации связей.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group_id: int | None = None
    schedule_id: int | None = None


class ScheduleGroupLinkUpdateSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для обновления связи.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        raise ValueError(
            "Связь расписания и группы нельзя обновлять. "
            "Удалите старую связь и создайте новую."
        )


class ScheduleGroupLinkDeleteSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для удаления связи по фильтру.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group_id: int | None = None
    schedule_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class ScheduleGroupLinkReadSchema(BaseReadSchema):
    """
    Схема чтения данных связи.
    """

    pass
