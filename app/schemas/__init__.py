"""
Пакет схем проекта.

Файл экспортирует базовые схемы и схемы сущности Group
для использования в остальных модулях приложения.
"""

from app.schemas.base import AppBaseSchema, BaseReadSchema, IdSchema, TimestampSchema
from app.schemas.group import (
    GroupBaseSchema,
    GroupCreateSchema,
    GroupDeleteSchema,
    GroupFilterSchema,
    GroupReadSchema,
    GroupUpdateSchema,
    is_group_name_formatted,
    is_speciality_formatted,
)

__all__ = [
    "AppBaseSchema",
    "IdSchema",
    "TimestampSchema",
    "BaseReadSchema",
    "GroupBaseSchema",
    "GroupCreateSchema",
    "GroupUpdateSchema",
    "GroupFilterSchema",
    "GroupDeleteSchema",
    "GroupReadSchema",
    "is_group_name_formatted",
    "is_speciality_formatted",
]
