"""
Схемы Pydantic для связи между расписанием и учебной группой.
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

    Описывает составной смысл записи: какая группа привязана к какой записи
    расписания.
    """

    group_id: int | None = None
    schedule_id: int | None = None


class ScheduleGroupLinkCreateSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для создания связи между группой и расписанием.
    """

    group_id: int
    schedule_id: int

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Убирает из входных данных служебные поля перед созданием связи.

        :param data: Невалидированные входные данные.
        :return: Данные без служебных полей.
        """
        return strip_service_fields(data)


class ScheduleGroupLinkFilterSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема фильтрации связей между группами и расписанием.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group_id: int | None = None
    schedule_id: int | None = None


class ScheduleGroupLinkUpdateSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема для обновления связи.

    Оставлена только для единообразия интерфейса сервисов. Логически такая
    связь не обновляется: старая запись удаляется, а новая создается заново.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Всегда запрещает обновление связи группы и расписания.

        :param data: Невалидированные входные данные.
        :return: Метод не возвращает значение, так как всегда выбрасывает
            исключение.
        :raises ValueError: Всегда, потому что обновление этой сущности не
            поддерживается.
        """
        raise ValueError(
            "Связь расписания и группы нельзя обновлять. "
            "Удалите старую связь и создайте новую."
        )


class ScheduleGroupLinkDeleteSchema(ScheduleGroupLinkBaseSchema):
    """
    Схема фильтра для удаления связи.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group_id: int | None = None
    schedule_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет, что удаление связи выполняется по непустому фильтру.

        :param data: Невалидированные входные данные.
        :return: Проверенный фильтр удаления.
        :raises ValueError: Если фильтр удаления пустой.
        """
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )


class ScheduleGroupLinkReadSchema(BaseReadSchema):
    """
    Заглушка для схемы чтения связи.
    """

    pass
