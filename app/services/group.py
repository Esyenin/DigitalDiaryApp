"""
Модуль сервиса для сущности Group.

Файл содержит класс GroupService.
GroupService настраивает BaseService для работы с моделью Group.

В модуле задаются:
- ORM-модель сервиса;
- схемы валидации для операций создания, выборки, обновления и удаления;
- список полей модели, которые разрешено извлекать для валидации.
"""
from app.models.group import Group
from app.schemas.group import (
    GroupCreateSchema,
    GroupDeleteSchema,
    GroupFilterSchema,
    GroupUpdateSchema,
)
from app.services.base import BaseService


class GroupService(BaseService[Group]):
    """
    Сервис для подготовки операций над моделью Group.

    Класс не реализует собственные методы CRUD.
    Класс задает параметры, которые использует BaseService:
    - `model` — ORM-модель сервиса;
    - `create_schema` — схема валидации для `create_instance`;
    - `select_schema` — схема валидации для `build_select`;
    - `update_schema` — схема валидации для `apply_update`;
    - `delete_schema` — схема валидации для `build_delete`;
    - `schema_fields` — поля модели, извлекаемые из ORM-объекта.

    Экземпляр GroupService подготавливает ORM-объекты Group,
    применяет изменения к существующему объекту Group и строит
    SQLAlchemy-выражения для операций выборки и удаления.
    Выполнение запросов, работа с сессией и транзакциями в класс не входят.
    """

    model = Group  # ORM-модель сервиса
    create_schema = GroupCreateSchema  # Схема создания
    select_schema = GroupFilterSchema  # Схема фильтрации
    update_schema = GroupUpdateSchema  # Схема обновления
    delete_schema = GroupDeleteSchema  # Схема удаления
    schema_fields = frozenset({"name", "speciality"})  # Поля ORM-объекта для извлечения
