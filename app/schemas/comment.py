"""
Схемы Pydantic для сущности комментария к занятию.
"""
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.comment import MAX_LEN
from app.schemas.base import (
    AppBaseSchema,
    strip_service_fields,
    validate_non_empty_mapping,
    validate_not_empty_string,
)


class CommentBaseSchema(AppBaseSchema):
    """
    Базовая схема комментария.

    Описывает текст комментария и ссылку на студента и занятие, к которым он
    относится.
    """

    student_id: int | None = None
    lesson_id: int | None = None
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @field_validator("data")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        """
        Проверяет поле текста комментария на недопустимую пустую строку.

        :param value: Значение текстового поля комментария.
        :return: Исходное значение, если оно допустимо.
        """
        return validate_not_empty_string(value)


class CommentCreateSchema(CommentBaseSchema):
    """
    Схема для создания комментария.
    """

    student_id: int
    lesson_id: int
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Убирает из входных данных служебные поля перед созданием комментария.

        :param data: Невалидированные входные данные.
        :return: Данные без служебных полей.
        """
        return strip_service_fields(data)


class CommentFilterSchema(CommentBaseSchema):
    """
    Схема фильтрации комментариев.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])


class CommentUpdateSchema(AppBaseSchema):
    """
    Схема для обновления комментария.

    Позволяет менять только текст комментария. Привязка к студенту и занятию
    в этой схеме не редактируется.
    """

    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @field_validator("data")
    @classmethod
    def validate_strings(cls, value: str | None) -> str | None:
        """
        Проверяет новое значение текста комментария.

        :param value: Обновляемый текст комментария.
        :return: Исходное значение, если оно допустимо.
        """
        return validate_not_empty_string(value)

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет, что в обновление передан непустой набор полей.

        :param data: Невалидированные входные данные.
        :return: Очищенный словарь обновляемых полей.
        :raises ValueError: Если обновлять нечего.
        """
        return validate_non_empty_mapping(
            strip_service_fields(data),
            "Для обновления нужно передать хотя бы одно поле.",
        )


class CommentDeleteSchema(CommentBaseSchema):
    """
    Схема фильтра для удаления комментариев.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    student_id: int | None = None
    lesson_id: int | None = None
    data: str | None = Field(default=None, max_length=MAX_LEN["data"])

    @model_validator(mode="before")
    @classmethod
    def validate_raw_data(cls, data: Any) -> Any:
        """
        Проверяет, что удаление выполняется по непустому фильтру.

        :param data: Невалидированные входные данные.
        :return: Проверенный фильтр удаления.
        :raises ValueError: Если фильтр удаления пустой.
        """
        return validate_non_empty_mapping(
            data,
            "Фильтр удаления не должен быть пустым.",
        )
