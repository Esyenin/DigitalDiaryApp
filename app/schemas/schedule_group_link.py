"""
Модуль схем для сущности ScheduleGroupLink.
"""
from typing import Any

from pydantic import model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
)


class ScheduleGroupLinkBaseSchema(AppBaseSchema):
    """
    Базовая схема связи расписания и группы.
    """

    group_id: int = None
    schedule_id: int = None


class ScheduleGroupLinkCreateSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для создания связи.
    """

    group_id: int
    schedule_id: int


class ScheduleGroupLinkFilterSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для фильтрации связей.
    """

    group_id: int = None
    schedule_id: int = None


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

    group_id: int = None
    schedule_id: int = None

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

    group_id: int
    schedule_id: int
