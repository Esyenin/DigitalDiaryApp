"""
Базовый сервис для одной SQLAlchemy-модели.

Модуль содержит общий слой подготовки ORM-объектов и SQLAlchemy-запросов.
Он не выполняет запросы к базе данных, не открывает сессии и не управляет
транзакциями. Эти обязанности остаются на более высоком уровне приложения.
"""
import logging
from typing import Generic, Mapping, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.sql import Delete, Select

from app.models.base import Base


ModelT = TypeVar("ModelT", bound=Base)
logger = logging.getLogger(__name__)


class BaseService(Generic[ModelT]):
    """
    Общая логика сервиса для одной ORM-модели.

    Класс связывает конкретную SQLAlchemy-модель с наборами Pydantic-схем
    для создания, чтения, обновления и удаления. Наследники задают модель
    и нужные схемы, а базовый класс выполняет преобразование входных данных,
    валидацию и построение ORM-объектов или SQLAlchemy-выражений.
    """

    model: type[ModelT]
    create_schema: type[BaseModel] | None = None
    select_schema: type[BaseModel] | None = None
    update_schema: type[BaseModel] | None = None
    delete_schema: type[BaseModel] | None = None
    schema_fields: frozenset[str] | None = None
    update_lookup_fields: frozenset[str] = frozenset({"id"})

    def _extract_model_data(
        self,
        obj: ModelT,
    ) -> dict[str, object]:
        """
        Извлекает публичные данные из ORM-объекта.

        :param obj: ORM-объект той модели, с которой работает сервис.

        :return: Словарь с полями объекта. Служебные атрибуты SQLAlchemy,
            начинающиеся с подчеркивания, в результат не попадают.
            Если `schema_fields` задан, возвращаются только поля из этого
            набора.
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

        :param obj: Данные в виде Pydantic-схемы, ORM-объекта, mapping-объекта
            или `None`.

        :return: Словарь с данными, которые можно передать в схему или модель.
            Для Pydantic-схем учитываются только явно переданные поля.
            Если на вход пришел `None`, возвращается `None`.
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
        Проверяет словарь через указанную Pydantic-схему.

        :param schema_class: Класс схемы, через которую нужно проверить данные.
            Если схема не задана, данные считаются уже допустимыми.
        :param data: Словарь данных для проверки или `None`.

        :return: Экземпляр Pydantic-схемы после успешной проверки, исходный
            словарь при отсутствии схемы или `None`, если данных нет либо
            валидация завершилась ошибкой.
        """
        if data is None:
            return None

        if schema_class is None:
            return data

        try:
            return schema_class.model_validate(data)
        except ValidationError:
            logger.warning(
                "Validation failed for %s.",
                schema_class.__name__,
                exc_info=True,
            )
            return None

    @staticmethod
    def _dump_validated_data(
        validated: BaseModel | dict[str, object],
    ) -> dict[str, object]:
        """
        Преобразует проверенные данные обратно в словарь.

        :param validated: Экземпляр Pydantic-схемы или уже готовый словарь.

        :return: Словарь с проверенными значениями. Для Pydantic-схем сохраняются
            только явно переданные поля.
        """
        if isinstance(validated, BaseModel):
            return validated.model_dump(exclude_unset=True)

        return dict(validated)

    def create_instance(
        self,
        data: BaseModel | ModelT | Mapping[str, object],
    ) -> ModelT | None:
        """
        Подготавливает ORM-объект для создания записи.

        :param data: Данные создаваемой записи в виде словаря, Pydantic-схемы
            или уже созданного ORM-объекта нужной модели.

        :return: ORM-объект, готовый к добавлению в SQLAlchemy-сессию. Если входные
            данные не проходят схему создания, возвращается `None`.
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
        Строит SQLAlchemy Select-запрос для модели сервиса.

        :param filters: Фильтр поиска в виде ORM-объекта, словаря, Pydantic-схемы
            или `None`. При `None` строится запрос без условий.

        :return: SQLAlchemy Select-выражение. Если фильтр не проходит схему чтения,
            возвращается `None`.
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
        Применяет данные обновления к существующему ORM-объекту.

        :param db_obj: ORM-объект, который уже относится к модели сервиса.
        :param data: Новые значения в виде ORM-объекта, словаря или
            Pydantic-схемы обновления.

        :return: Тот же ORM-объект после применения допустимых изменений. Поля,
            перечисленные в `update_lookup_fields`, не изменяются. Если объект
            относится к другой модели или данные не проходят схему обновления,
            возвращается `None`.
        """
        if not isinstance(db_obj, self.model):
            return None

        raw_data = self._extract_data(data)
        validated = self._validate(self.update_schema, raw_data)
        if validated is None:
            return None

        for field_name, value in self._dump_validated_data(validated).items():
            if field_name in self.update_lookup_fields:
                continue
            setattr(db_obj, field_name, value)

        return db_obj

    def build_delete(
        self,
        filters: ModelT | Mapping[str, object] | BaseModel | None,
    ) -> Delete | None:
        """
        Строит SQLAlchemy Delete-запрос для модели сервиса.

        :param filters: Фильтр удаления в виде ORM-объекта, словаря,
            Pydantic-схемы или `None`.

        :return: SQLAlchemy Delete-выражение с условиями из фильтра. Если фильтр
            не проходит схему удаления, возвращается `None`.
        """
        raw_data = self._extract_data(filters)
        validated = self._validate(self.delete_schema, raw_data)
        if validated is None:
            return None

        return sa_delete(self.model).filter_by(
            **self._dump_validated_data(validated)
        )

    def create(
        self,
        data: BaseModel | ModelT | Mapping[str, object],
    ) -> ModelT | None:
        """
        Совместимый короткий вызов для `create_instance`.

        :param data: Данные создаваемой записи.

        :return: ORM-объект для создания записи или `None`, если данные отклонены.
        """
        return self.create_instance(data)

    def get(
        self,
        filters: ModelT | Mapping[str, object] | BaseModel | None = None,
    ) -> Select | None:
        """
        Совместимый короткий вызов для `build_select`.

        :param filters: Фильтр поиска или `None`.

        :return: SQLAlchemy Select-выражение или `None`, если фильтр отклонен.
        """
        return self.build_select(filters)

    def update(
        self,
        db_obj: ModelT,
        data: ModelT | Mapping[str, object] | BaseModel,
    ) -> ModelT | None:
        """
        Совместимый короткий вызов для `apply_update`.

        :param db_obj: ORM-объект, который нужно изменить.
        :param data: Данные обновления.

        :return: Измененный ORM-объект или `None`, если обновление отклонено.
        """
        return self.apply_update(db_obj, data)

    def delete(
        self,
        filters: ModelT | Mapping[str, object] | BaseModel | None,
    ) -> Delete | None:
        """
        Совместимый короткий вызов для `build_delete`.

        :param filters: Фильтр удаления.

        :return: SQLAlchemy Delete-выражение или `None`, если фильтр отклонен.
        """
        return self.build_delete(filters)
