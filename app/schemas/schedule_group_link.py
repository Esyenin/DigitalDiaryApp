"""
Модуль схем для сущности ScheduleGroupLink.
"""
from typing import Any

from pydantic import model_validator

from app.schemas.base import (
    AppBaseSchema,
    BaseReadSchema,
    validate_non_empty_mapping,
    validate_not_none_fields,
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


class ScheduleGroupLinkFilterSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для фильтрации связей.
    """


class ScheduleGroupLinkUpdateSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для обновления связи.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        validated = validate_non_empty_mapping(
            data,
            "Для обновления нужно передать хотя бы одно поле.",
        )
        validate_not_none_fields(validated, ("group_id", "schedule_id"))
        return validated


class ScheduleGroupLinkDeleteSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для удаления связи по фильтру.
    """

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
