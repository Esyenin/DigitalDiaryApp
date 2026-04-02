"""
Модуль базового сервиса.

Файл содержит класс BaseService.
BaseService задает общий интерфейс и общее поведение сервисов,
работающих с одной SQLAlchemy-моделью.

Модуль определяет:
- контракт базового сервиса;
- правила нормализации входных данных;
- правила валидации данных через Pydantic-схемы;
- подготовку ORM-объектов;
- построение SQLAlchemy-выражений Select и Delete;
- применение изменений к существующему ORM-объекту.
"""
from typing import Generic, Mapping, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.sql import Delete, Select

from app.models.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseService(Generic[ModelT]):
    """
    Базовый сервис для одной ORM-модели.

    Класс предназначен для наследования.
    Наследник должен задать:
    - `model` — ORM-модель сервиса;
    - `create_schema` — схему валидации для `create_instance`;
    - `select_schema` — схему валидации для `build_select`;
    - `update_schema` — схему валидации для `apply_update`;
    - `delete_schema` — схему валидации для `build_delete`;
    - `schema_fields` — набор полей, извлекаемых из ORM-объекта.

    Класс не выполняет SQL-запросы, не работает с сессией базы данных
    и не управляет транзакциями.
    """

    model: type[ModelT]
    create_schema: type[BaseModel] | None = None
    select_schema: type[BaseModel] | None = None
    update_schema: type[BaseModel] | None = None
    delete_schema: type[BaseModel] | None = None
    schema_fields: frozenset[str] | None = None

    def _extract_model_data(self, obj: ModelT) -> dict[str, object]:
        """
        Извлекает данные из ORM-объекта.

        Метод читает атрибуты объекта из `__dict__`, исключает служебные поля
        SQLAlchemy, начинающиеся с `_`, и при необходимости оставляет только
        поля из `schema_fields`.

        Args:
            obj: Экземпляр ORM-модели, связанной с сервисом.

        Returns:
            dict[str, object]: Словарь с полями объекта.
        """
        data = {
            key: value
            for key, value in obj.__dict__.items()
            if not key.startswith("_")
        }

        if self.schema_fields is None:
            return data

        return {
            key: value
            for key, value in data.items()
            if key in self.schema_fields
        }

    def _extract_data(
        self,
        obj: BaseModel | ModelT | Mapping[str, object] | None,
    ) -> dict[str, object] | None:
        """
        Приводит входные данные к словарю.

        Поддерживаемые типы входа:
        - `None`;
        - Mapping;
        - экземпляр Pydantic-модели;
        - экземпляр ORM-модели.

        Для Pydantic-модели используется `model_dump(exclude_unset=True)`.
        Для ORM-модели используется `_extract_model_data`.

        Args:
            obj: Данные для преобразования.

        Returns:
            dict[str, object] | None: Словарь данных или `None`.
        """
        if obj is None:
            return None

        if isinstance(obj, BaseModel):
            return obj.model_dump(exclude_unset=True)

        if isinstance(obj, Mapping):
            return dict(obj)

        return self._extract_model_data(obj)

    @staticmethod
    def _validate(
        schema_class: type[BaseModel] | None,
        data: dict[str, object] | None,
    ) -> BaseModel | dict[str, object] | None:
        """
        Валидирует словарь через переданную схему.

        Если `schema_class` равен `None`, метод возвращает исходные данные.
        Если валидация не пройдена, метод возвращает `None`.

        Args:
            schema_class: Класс Pydantic-схемы для проверки данных.
            data: Словарь данных, который нужно провалидировать.

        Returns:
            BaseModel | dict[str, object] | None: Результат валидации
            или `None`.
        """
        if data is None:
            return None

        if schema_class is None:
            return data

        try:
            return schema_class.model_validate(data)
        except ValidationError:
            return None

    @staticmethod
    def _dump_validated_data(
        validated: BaseModel | dict[str, object],
    ) -> dict[str, object]:
        """
        Преобразует результат валидации в словарь.

        Если передан экземпляр Pydantic-модели, используется
        `model_dump(exclude_unset=True)`.
        Если передан словарь, он копируется в новый `dict`.

        Args:
            validated: Результат предыдущей валидации.

        Returns:
            dict[str, object]: Словарь данных.
        """
        if isinstance(validated, BaseModel):
            return validated.model_dump(exclude_unset=True)

        return dict(validated)

    def create_instance(
        self,
        data: BaseModel | ModelT | Mapping[str, object],
    ) -> ModelT | None:
        """
        Подготавливает ORM-объект для создания.

        Метод:
        1. преобразует входные данные в словарь;
        2. валидирует их через `create_schema`;
        3. возвращает экземпляр `self.model`.

        Если на вход уже передан объект `self.model`, после успешной валидации
        возвращается этот же объект.

        Args:
            data: Данные для создания объекта.

        Returns:
            ModelT | None: Экземпляр ORM-модели или `None`.
        """
        raw_data = self._extract_data(data)
        validated = self._validate(self.create_schema, raw_data)
        if validated is None:
            return None

        if isinstance(data, self.model):
            return data

        return self.model(**self._dump_validated_data(validated))

    def build_select(
        self,
        filters: ModelT | Mapping[str, object] | BaseModel | None = None,
    ) -> Select | None:
        """
        Строит Select-выражение для модели.

        Если `filters` равен `None`, метод возвращает `select(self.model)`.
        Если фильтры переданы, они валидируются через `select_schema`
        и применяются к выражению через `filter_by`.

        Args:
            filters: Фильтры выборки.

        Returns:
            Select | None: SQLAlchemy Select или `None`.
        """
        stmt = select(self.model)
        if filters is None:
            return stmt

        raw_data = self._extract_data(filters)
        validated = self._validate(self.select_schema, raw_data)
        if validated is None:
            return None

        filter_data = self._dump_validated_data(validated)
        if filter_data:
            stmt = stmt.filter_by(**filter_data)

        return stmt

    def apply_update(
        self,
        db_obj: ModelT,
        data: ModelT | Mapping[str, object] | BaseModel,
    ) -> ModelT | None:
        """
        Применяет изменения к существующему ORM-объекту.

        Метод проверяет тип `db_obj`, валидирует `data` через `update_schema`
        и присваивает новые значения полям объекта через `setattr`.

        Args:
            db_obj: Объект модели, который нужно изменить.
            data: Новые значения полей.

        Returns:
            ModelT | None: Обновленный объект или `None`.
        """
        if not isinstance(db_obj, self.model):
            return None

        raw_data = self._extract_data(data)
        validated = self._validate(self.update_schema, raw_data)
        if validated is None:
            return None

        for field_name, value in self._dump_validated_data(validated).items():
            setattr(db_obj, field_name, value)

        return db_obj

    def build_delete(
        self,
        filters: ModelT | Mapping[str, object] | BaseModel | None,
    ) -> Delete | None:
        """
        Строит Delete-выражение для модели.

        Метод валидирует `filters` через `delete_schema`
        и возвращает `delete(self.model).filter_by(...)`.

        Args:
            filters: Фильтры удаления.

        Returns:
            Delete | None: SQLAlchemy Delete или `None`.
        """
        raw_data = self._extract_data(filters)
        validated = self._validate(self.delete_schema, raw_data)
        if validated is None:
            return None

        return sa_delete(self.model).filter_by(
            **self._dump_validated_data(validated)
        )
