"""
Модуль базового сервиса.

Файл содержит класс BaseService.
BaseService задает общий интерфейс и общее поведение сервисов,
работающих с одной SQLAlchemy-моделью.
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

    Наследник задает:
    - `model` - ORM-модель сервиса;
    - `create_schema` - схему валидации для создания;
    - `select_schema` - схему валидации для выборки;
    - `update_schema` - схему валидации для обновления;
    - `delete_schema` - схему валидации для удаления;
    - `schema_fields` - поля модели, разрешенные для извлечения из ORM-объекта.

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
        """
        raw_data = self._extract_data(filters)
        validated = self._validate(self.delete_schema, raw_data)
        if validated is None:
            return None

        return sa_delete(self.model).filter_by(
            **self._dump_validated_data(validated)
        )

    # Совместимость со старым API сервисов.
    def create(
        self,
        data: BaseModel | ModelT | Mapping[str, object],
    ) -> ModelT | None:
        return self.create_instance(data)

    def get(
        self,
        filters: ModelT | Mapping[str, object] | BaseModel | None = None,
    ) -> Select | None:
        return self.build_select(filters)

    def update(
        self,
        db_obj: ModelT,
        data: ModelT | Mapping[str, object] | BaseModel,
    ) -> ModelT | None:
        return self.apply_update(db_obj, data)

    def delete(
        self,
        filters: ModelT | Mapping[str, object] | BaseModel | None,
    ) -> Delete | None:
        return self.build_delete(filters)
