"""
Модуль базовых Pydantic-схем.

Файл содержит общие схемы, используемые в остальных модулях пакета:
- базовую схему проекта;
- схему с полем идентификатора;
- схему с временными метками;
- базовую схему чтения данных из БД.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppBaseSchema(BaseModel):
    """
    Базовая схема проекта.

    Класс задает общую конфигурацию Pydantic-моделей.
    От этого класса наследуются прикладные схемы проекта.
    """

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class IdSchema(AppBaseSchema):
    """
    Схема с полем идентификатора записи.
    """

    id: int


class TimestampSchema(AppBaseSchema):
    """
    Схема с полями времени создания и обновления записи.
    """

    created_at: datetime
    updated_at: datetime


class BaseReadSchema(IdSchema, TimestampSchema):
    """
    Базовая схема чтения данных из БД.

    Класс содержит поля:
    - `id`;
    - `created_at`;
    - `updated_at`.
    """

    pass
