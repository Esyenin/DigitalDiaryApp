"""
Общий ORM-фасад приложения.

Модуль содержит сервис верхнего уровня, который автоматически находит
сервисы конкретных сущностей, определяет нужный сервис по входным данным,
управляет SQLAlchemy-сессией и выполняет CRUD-операции через единый API.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import importlib
import inspect
import logging
from pathlib import Path
import pkgutil
import re
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.io_tools import ImportExportService
from app.io_tools.xlsx_config import normalize_sheet_keys
import app.services as services_package
from app.models import Base
from app.services.base import BaseService


Payload = BaseModel | Base | Mapping[str, object]
Operation = Literal["create", "get", "update", "delete"]

logger = logging.getLogger(__name__)


class OrmServiceError(Exception):
    """
    Базовое исключение ORM-фасада.

    Используется как общий родитель для ошибок, связанных не с конкретной
    таблицей, а с работой самого `OrmService`: определением сервиса,
    неоднозначностью входных данных или неверной настройкой сессии.
    """


class UnknownServiceError(OrmServiceError):
    """
    Ошибка, возникающая при невозможности определить сервис сущности.

    Исключение означает, что по переданному ORM-объекту, Pydantic-схеме или
    словарю не найден ни один сервис, который может обработать операцию.
    """


class AmbiguousServiceError(OrmServiceError):
    """
    Ошибка неоднозначного определения сервиса сущности.

    Исключение означает, что один и тот же словарь подходит схемам нескольких
    сервисов, поэтому фасад не может безопасно выбрать модель сам.
    """


class OrmService:
    """
    Фасад для работы с ORM-операциями приложения.

    Класс скрывает от внешнего кода детали выбора конкретного сервиса
    сущности. Пользователь передает ORM-объект, Pydantic-схему или словарь,
    а фасад сам выбирает подходящий сервис, вызывает его методы и применяет
    результат к SQLAlchemy-сессии.

    Публичные методы:
        create: создает ORM-объект и добавляет его в сессию.

        get: получает список ORM-объектов по фильтру.

        update: обновляет найденные ORM-объекты.

        delete: удаляет ORM-объекты по фильтру или переданному объекту.

        commit: подтверждает текущую транзакцию.

        rollback: откатывает текущую транзакцию.

        close: закрывает текущую SQLAlchemy-сессию.
    """

    _schema_attr_by_operation = {
        "create": "create_schema",
        "get": "select_schema",
        "update": "update_schema",
        "delete": "delete_schema",
    }

    def __init__(
        self,
        session: Session | None = None,
        *,
        session_factory: sessionmaker | None = None,
        auto_commit: bool = True,
        close_on_exit: bool = True,
        service_logger: logging.Logger | None = None,
    ) -> None:
        """
        Инициализирует ORM-фасад и регистрирует найденные сервисы.

        :param session: Готовая SQLAlchemy-сессия. Если передана, фасад будет
            работать именно с ней.
        :param session_factory: Фабрика, создающая SQLAlchemy-сессию. Используется
            только если готовая `session` не передана.
        :param auto_commit: Если `True`, write-операции завершаются `commit`.
            Если `False`, после write-операций выполняется только `flush`.
        :param close_on_exit: Нужно ли закрывать сессию при выходе из context
            manager.
        :param service_logger: Logger, который будет использовать фасад. Если
            параметр не передан, используется logger этого модуля.

        :raises OrmServiceError: Если не передана ни готовая сессия, ни фабрика
            сессий.
        """
        self.logger = service_logger or logger
        self.logger.debug("OrmService initialization started.")

        if session is None and session_factory is None:
            self.logger.error(
                "OrmService initialization failed: no session provider."
            )
            raise OrmServiceError("session or session_factory is required.")

        self.session = session if session is not None else session_factory()
        self.auto_commit = auto_commit
        self.close_on_exit = close_on_exit
        self._services_by_model: dict[type[Base], BaseService[Any]] = {}
        self._services_by_schema: dict[type[BaseModel], BaseService[Any]] = {}
        self._import_export_service = ImportExportService()

        for service in self._build_services():
            self._register_service(service)

        self.logger.info(
            "OrmService initialized. services_count=%s.",
            len(self._services_by_model),
        )

    def __enter__(self) -> OrmService:
        """
        Входит в context manager для работы с ORM-фасадом.

        :return: Текущий экземпляр `OrmService`, с которым будет работать блок
            `with`.
        """
        self.logger.info("OrmService context enter.")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        """
        Завершает работу context manager.

        :param exc_type: Тип исключения, возникшего внутри блока `with`, или
            `None`, если блок завершился успешно.
        :param exc_value: Экземпляр исключения или `None`.
        :param traceback: Объект traceback для возникшего исключения или `None`.

        :return: `False`, чтобы исключения из блока `with` не подавлялись и могли
            быть обработаны вызывающим кодом.
        """
        self.logger.info("OrmService context exit started.")

        if exc_type is not None:
            self.rollback()
            self.logger.error(
                "OrmService context exited with error.",
                exc_info=(exc_type, exc_value, traceback),
            )
        elif self.auto_commit:
            self.commit()

        if self.close_on_exit:
            self.close()

        self.logger.info("OrmService context exit finished.")
        return False

    @classmethod
    def _discover_service_classes(cls) -> tuple[type[BaseService[Any]], ...]:
        """
        Находит классы сервисов сущностей в пакете `app.services`.

        Метод просматривает модули пакета сервисов, пропускает базовые и
        служебные модули, импортирует остальные и выбирает классы, которые
        наследуются от `BaseService` и явно объявляют ORM-модель.

        :return: Кортеж классов сервисов, доступных для автоматической регистрации.
        """
        discovered: list[type[BaseService[Any]]] = []
        logger.debug("Service discovery started.")

        for module_info in pkgutil.iter_modules(services_package.__path__):
            if module_info.name in {"base", "ormservice", "__init__"}:
                logger.debug(
                    "Service discovery skipped module=%s.",
                    module_info.name,
                )
                continue

            module = importlib.import_module(
                f"{services_package.__name__}.{module_info.name}"
            )

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj is BaseService:
                    continue
                if not issubclass(obj, BaseService):
                    continue
                if obj.__module__ != module.__name__:
                    continue
                if getattr(obj, "model", None) is None:
                    logger.debug(
                        "Service discovery skipped class=%s without model.",
                        obj.__name__,
                    )
                    continue

                discovered.append(obj)
                logger.debug("Service discovered: %s.", obj.__name__)

        logger.info("Service discovery finished. count=%s.", len(discovered))
        return tuple(discovered)

    @classmethod
    def _build_services(cls) -> tuple[BaseService[Any], ...]:
        """
        Создает экземпляры автоматически найденных сервисов.

        :return: Кортеж готовых экземпляров сервисов сущностей.
        """
        logger.debug("Service building started.")
        services = tuple(
            service_class()
            for service_class in cls._discover_service_classes()
        )
        logger.info("Service building finished. count=%s.", len(services))
        return services

    def _register_service(self, service: BaseService[Any]) -> None:
        """
        Регистрирует сервис во внутренних индексах фасада.

        :param service: Экземпляр сервиса конкретной сущности. Сервис должен
            иметь поле `model` и набор схем, по которым фасад сможет
            определять его для разных операций.

        :return: `None`. Метод изменяет внутренние словари регистрации.
        """
        self._services_by_model[service.model] = service

        for schema in self._service_schemas(service):
            self._services_by_schema[schema] = service

        self.logger.debug(
            "Service registered. service=%s model=%s.",
            service.__class__.__name__,
            service.model.__name__,
        )

    def _service_schemas(
        self,
        service: BaseService[Any],
    ) -> tuple[type[BaseModel], ...]:
        """
        Собирает схемы, объявленные в сервисе сущности.

        :param service: Сервис, из которого нужно получить схемы создания,
            чтения, обновления и удаления.

        :return: Кортеж Pydantic-схем, найденных в сервисе. Отсутствующие схемы
            в результат не добавляются.
        """
        schemas = []

        for attr_name in self._schema_attr_by_operation.values():
            schema = getattr(service, attr_name, None)
            if schema is not None:
                schemas.append(schema)

        return tuple(schemas)

    def _schema_for_operation(
        self,
        service: BaseService[Any],
        operation: Operation,
    ) -> type[BaseModel] | None:
        """
        Возвращает схему сервиса для конкретной CRUD-операции.

        :param service: Сервис сущности, у которого нужно взять схему.
        :param operation: Имя операции: `create`, `get`, `update` или `delete`.

        :return: Класс Pydantic-схемы для операции или `None`, если у сервиса нет
            соответствующей схемы.
        """
        return getattr(service, self._schema_attr_by_operation[operation], None)

    def _extract_data(self, data: Payload | None) -> dict[str, object] | None:
        """
        Приводит входные данные фасада к обычному словарю.

        :param data: ORM-объект, Pydantic-схема, mapping-объект или `None`.

        :return: Словарь с публичными значениями payload. Для Pydantic-схем
            возвращаются только явно переданные поля. Для ORM-объектов
            исключаются служебные атрибуты SQLAlchemy. Если тип не
            поддерживается, возвращается `None`.
        """
        if data is None:
            self.logger.debug("Payload extraction skipped: payload is None.")
            return None

        if isinstance(data, BaseModel):
            self.logger.debug(
                "Payload extracted from Pydantic schema=%s.",
                data.__class__.__name__,
            )
            return data.model_dump(exclude_unset=True)

        if isinstance(data, Mapping):
            self.logger.debug("Payload extracted from mapping.")
            return dict(data)

        if isinstance(data, Base):
            self.logger.debug(
                "Payload extracted from ORM object=%s.",
                data.__class__.__name__,
            )
            return {
                key: value
                for key, value in data.__dict__.items()
                if not key.startswith("_")
            }

        self.logger.warning(
            "Payload extraction failed: unsupported type=%s.",
            type(data).__name__,
        )
        return None

    @staticmethod
    def _schema_accepts(
        schema: type[BaseModel] | None,
        data: dict[str, object] | None,
    ) -> bool:
        """
        Проверяет, принимает ли схема переданный словарь.

        :param schema: Pydantic-схема, через которую нужно проверить данные.
        :param data: Словарь данных для проверки.

        :return: `True`, если схема существует и данные успешно валидируются.
            `False`, если схемы нет, данных нет или проверка завершилась
            ошибкой.
        """
        if schema is None or data is None:
            return False

        try:
            schema.model_validate(data)
        except ValidationError:
            return False

        return True

    def _service_from_model(self, model: type[Base]) -> BaseService[Any]:
        """
        Находит сервис по классу ORM-модели.

        :param model: Класс SQLAlchemy-модели, для которой нужен сервис.

        :return: Зарегистрированный сервис, связанный с моделью.

        :raises UnknownServiceError: Если для модели не зарегистрирован сервис.
        """
        service = self._services_by_model.get(model)
        if service is None:
            self.logger.error(
                "Service resolving failed: unknown model=%s.",
                model.__name__,
            )
            raise UnknownServiceError(
                f"No service registered for model {model.__name__}."
            )

        return service

    def _service_from_schema(self, schema: BaseModel) -> BaseService[Any] | None:
        """
        Находит сервис по экземпляру Pydantic-схемы.

        :param schema: Экземпляр схемы, который был передан во внешний CRUD-метод.

        :return: Сервис, зарегистрированный для класса этой схемы, или `None`, если
            подходящий сервис не найден.
        """
        service = self._services_by_schema.get(type(schema))
        if service is not None:
            return service

        for schema_class, candidate in self._services_by_schema.items():
            if isinstance(schema, schema_class):
                return candidate

        return None

    def _matching_services(
        self,
        data: Payload,
        operation: Operation,
    ) -> list[BaseService[Any]]:
        """
        Ищет сервисы, схемы которых принимают переданный payload.

        :param data: Payload операции в виде ORM-объекта, Pydantic-схемы или
            mapping-объекта.
        :param operation: Операция, для которой подбирается сервис.

        :return: Список сервисов, чьи схемы для указанной операции успешно приняли
            данные.
        """
        raw_data = self._extract_data(data)
        if raw_data is None:
            return []

        matches = []

        for service in self._services_by_model.values():
            schema = self._schema_for_operation(service, operation)
            if self._schema_accepts(schema, raw_data):
                matches.append(service)

        self.logger.debug(
            "Service matching finished. operation=%s matches=%s.",
            operation,
            [service.model.__name__ for service in matches],
        )
        return matches

    def _resolve_service(
        self,
        data: Payload,
        operation: Operation,
    ) -> BaseService[Any]:
        """
        Определяет сервис, который должен обработать операцию.

        :param data: Payload операции. ORM-объект определяет сервис по своему
            классу, Pydantic-схема - по классу схемы, словарь - через
            проверку схем всех сервисов.
        :param operation: Операция, для которой нужен сервис.

        :return: Единственный сервис, подходящий для payload и операции.

        :raises UnknownServiceError: Если сервис определить невозможно.
        :raises AmbiguousServiceError: Если словарь подходит нескольким сервисам.
        """
        self.logger.debug(
            "Service resolving started. operation=%s payload_type=%s.",
            operation,
            type(data).__name__,
        )

        if isinstance(data, Base):
            service = self._service_from_model(type(data))
            self.logger.debug(
                "Service resolved by ORM object. service=%s.",
                service.__class__.__name__,
            )
            return service

        if isinstance(data, BaseModel):
            service = self._service_from_schema(data)
            if service is None:
                self.logger.error(
                    "Service resolving failed: unknown schema=%s.",
                    data.__class__.__name__,
                )
                raise UnknownServiceError(
                    f"No service registered for schema "
                    f"{data.__class__.__name__}."
                )

            self.logger.debug(
                "Service resolved by Pydantic schema. service=%s.",
                service.__class__.__name__,
            )
            return service

        if not isinstance(data, Mapping):
            self.logger.error(
                "Service resolving failed: unsupported payload type=%s.",
                type(data).__name__,
            )
            raise UnknownServiceError(
                f"Unsupported payload type: {type(data).__name__}."
            )

        matches = self._matching_services(data, operation)

        if not matches:
            self.logger.error(
                "Service resolving failed: no matching service. "
                "operation=%s payload=%r.",
                operation,
                data,
            )
            raise UnknownServiceError(
                f"Payload does not match any service for {operation}."
            )

        if len(matches) > 1:
            names = ", ".join(service.model.__name__ for service in matches)
            self.logger.error(
                "Service resolving failed: ambiguous payload. "
                "operation=%s matches=%s payload=%r.",
                operation,
                names,
                data,
            )
            raise AmbiguousServiceError(
                f"Payload is ambiguous for {operation}. "
                f"Matching models: {names}."
            )

        self.logger.debug(
            "Service resolved by payload. service=%s.",
            matches[0].__class__.__name__,
        )
        return matches[0]

    def _resolve_update_service(
        self,
        filters_or_obj: Payload,
        data: Payload,
    ) -> BaseService[Any]:
        """
        Определяет сервис для операции обновления.

        :param filters_or_obj: ORM-объект для прямого обновления или фильтр,
            по которому нужно найти обновляемые объекты.
        :param data: Payload с изменяемыми полями.

        :return: Сервис сущности, которую нужно обновлять.

        :raises OrmServiceError: Если сервис нельзя определить ни по объекту,
            ни по данным обновления, ни по фильтру.
        """
        if isinstance(filters_or_obj, Base):
            return self._service_from_model(type(filters_or_obj))

        resolving_errors: list[OrmServiceError] = []

        for payload, operation in ((data, "update"), (filters_or_obj, "get")):
            try:
                return self._resolve_service(payload, operation)
            except OrmServiceError as exc:
                resolving_errors.append(exc)

        raise resolving_errors[0]

    def _filter_data(self, filters: Payload) -> dict[str, object] | None:
        """
        Приводит фильтр операции к словарю.

        :param filters: Фильтр в виде ORM-объекта, Pydantic-схемы или
            mapping-объекта.

        :return: Словарь фильтра или `None`, если фильтр нельзя преобразовать.
        """
        return self._extract_data(filters)

    def _select_objects(
        self,
        service: BaseService[Any],
        filters: Payload,
    ) -> list[Base] | None:
        """
        Выполняет выборку ORM-объектов через конкретный сервис.

        :param service: Сервис сущности, который строит Select-запрос.
        :param filters: Фильтр выборки, переданный пользователем фасада.

        :return: Список найденных ORM-объектов. Если фильтр отклонен схемой или
            база данных вернула ошибку, возвращается `None`.
        """
        filter_data = self._filter_data(filters)
        stmt = service.build_select(filter_data)

        if stmt is None:
            self.logger.warning(
                "Select rejected. service=%s filters=%r.",
                service.__class__.__name__,
                filters,
            )
            return None

        try:
            result = list(self.session.scalars(stmt).all())
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception(
                "Select failed. service=%s filters=%r.",
                service.__class__.__name__,
                filters,
            )
            return None

        self.logger.info(
            "Select finished. model=%s count=%s.",
            service.model.__name__,
            len(result),
        )
        return result

    @staticmethod
    def _sheet_key_from_model(model: type[Base]) -> str:
        """
        Приводит ORM-модель к каноническому ключу XLSX-листа.

        :param model: Класс ORM-модели, зарегистрированной в фасаде.
        :return: Канонический ключ листа XLSX для этой модели.
        :raises OrmServiceError: Если для модели не удалось определить ключ листа.
        """
        model_name = re.sub(r"(?<!^)(?=[A-Z])", "_", model.__name__).lower()

        try:
            return normalize_sheet_keys([model_name])[0]
        except (IndexError, ValueError) as exc:
            raise OrmServiceError(
                f"Cannot resolve XLSX sheet key for model {model.__name__}."
            ) from exc

    def _service_from_sheet_key(self, sheet_key: str) -> BaseService[Any]:
        """
        Находит сервис по каноническому ключу XLSX-листа.

        :param sheet_key: Каноническое имя листа XLSX.
        :return: Сервис сущности, соответствующий переданному листу.
        :raises UnknownServiceError: Если ни один сервис не связан с этим листом.
        """
        for model, service in self._services_by_model.items():
            if self._sheet_key_from_model(model) == sheet_key:
                return service

        self.logger.error(
            "Service resolving failed: unknown XLSX sheet key=%s.",
            sheet_key,
        )
        raise UnknownServiceError(
            f"No service registered for XLSX sheet key {sheet_key}."
        )

    def _export_payload_for_sheet_keys(
        self,
        sheet_keys: Sequence[str],
    ) -> dict[str, list[Base]]:
        """
        Собирает данные из базы для экспорта по набору листов.

        :param sheet_keys: Канонические ключи листов XLSX, которые нужно выгрузить.
        :return: Словарь, где ключом является имя листа, а значением список ORM-объектов.
        :raises OrmServiceError: Если получение данных для одного из листов завершилось ошибкой.
        """
        export_payload: dict[str, list[Base]] = {}

        for sheet_key in sheet_keys:
            service = self._service_from_sheet_key(sheet_key)
            objects = self._select_objects(service, {})

            if objects is None:
                raise OrmServiceError(
                    f"Failed to collect export data for sheet {sheet_key}."
                )

            export_payload[sheet_key] = objects

        return export_payload

    def _save(self, action: str) -> bool:
        """
        Сохраняет изменения текущей операции в SQLAlchemy-сессии.

        :param action: Название операции, ради которой выполняется сохранение.
            Используется только для логирования.

        :return: `True`, если `commit` или `flush` прошел успешно. `False`, если
            SQLAlchemy вернула ошибку и изменения были откатаны.
        """
        self.logger.debug("Save started. action=%s.", action)

        try:
            if self.auto_commit:
                self.session.commit()
                self.logger.info("Commit finished. action=%s.", action)
            else:
                self.session.flush()
                self.logger.info("Flush finished. action=%s.", action)
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception("Save failed. action=%s.", action)
            return False

        return True

    def create(self, data: Payload) -> Base | None:
        """
        Создает ORM-объект и добавляет его в текущую сессию.

        :param data: Данные создаваемой записи в виде словаря, Pydantic-схемы
            или ORM-объекта.

        :return: Созданный ORM-объект после добавления в сессию и сохранения
            изменений. Если данные отклонены схемой или сохранение завершилось
            ошибкой, возвращается `None`.

        :raises OrmServiceError: Если фасад не может определить сервис по payload.
        """
        self.logger.info("Create started. payload_type=%s.", type(data).__name__)

        service = self._resolve_service(data, "create")
        instance = service.create_instance(data)

        if instance is None:
            self.logger.warning(
                "Create rejected. service=%s payload=%r.",
                service.__class__.__name__,
                data,
            )
            return None

        try:
            self.session.add(instance)
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception(
                "Create failed while adding object. model=%s.",
                service.model.__name__,
            )
            return None

        if not self._save("create"):
            return None

        self.logger.info(
            "Create finished. model=%s id=%s.",
            service.model.__name__,
            getattr(instance, "id", None),
        )
        return instance

    def get(self, filters: Payload) -> list[Base]:
        """
        Получает ORM-объекты по фильтру.

        :param filters: Фильтр поиска в виде словаря, Pydantic-схемы или
            ORM-объекта.

        :return: Список найденных ORM-объектов. Если фильтр отклонен или при
            выполнении запроса произошла ошибка, возвращается пустой список.

        :raises OrmServiceError: Если фасад не может определить сервис по фильтру.
        """
        self.logger.info("Get started. payload_type=%s.", type(filters).__name__)

        service = self._resolve_service(filters, "get")
        objects = self._select_objects(service, filters)

        if objects is None:
            self.logger.warning(
                "Get rejected. service=%s filters=%r.",
                service.__class__.__name__,
                filters,
            )
            return []

        self.logger.info(
            "Get finished. model=%s count=%s.",
            service.model.__name__,
            len(objects),
        )
        return objects

    def update(
        self,
        filters_or_obj: Payload,
        data: Payload,
    ) -> list[Base] | None:
        """
        Обновляет ORM-объекты.

        :param filters_or_obj: ORM-объект для прямого обновления или фильтр,
            по которому нужно найти объекты в базе данных.
        :param data: Данные обновления в виде словаря, Pydantic-схемы или
            ORM-объекта.

        :return: Список обновленных ORM-объектов. Если фильтр, данные обновления
            или сохранение отклонены, возвращается `None`.

        :raises OrmServiceError: Если фасад не может определить сервис для
            операции обновления.
        """
        self.logger.info(
            "Update started. target_type=%s payload_type=%s.",
            type(filters_or_obj).__name__,
            type(data).__name__,
        )

        service = self._resolve_update_service(filters_or_obj, data)

        if isinstance(filters_or_obj, service.model):
            objects = [filters_or_obj]
            self.logger.debug(
                "Update target resolved as ORM object. model=%s.",
                service.model.__name__,
            )
        else:
            selected = self._select_objects(service, filters_or_obj)
            if selected is None:
                return None
            objects = selected

        updated_objects = []

        for db_obj in objects:
            updated = service.apply_update(db_obj, data)
            if updated is None:
                self.logger.warning(
                    "Update rejected. service=%s payload=%r.",
                    service.__class__.__name__,
                    data,
                )
                return None
            updated_objects.append(updated)

        if not self._save("update"):
            return None

        self.logger.info(
            "Update finished. model=%s count=%s.",
            service.model.__name__,
            len(updated_objects),
        )
        return updated_objects

    def delete(self, filters: Payload) -> int | None:
        """
        Удаляет ORM-объекты по фильтру или переданному объекту.

        :param filters: Фильтр удаления в виде словаря, Pydantic-схемы или
            ORM-объекта. Если передан persistent ORM-объект, он удаляется
            через `session.delete`.

        :return: Количество удаленных записей. Если фильтр отклонен или операция
            удаления завершилась ошибкой, возвращается `None`.

        :raises OrmServiceError: Если фасад не может определить сервис по фильтру.
        """
        self.logger.info(
            "Delete started. payload_type=%s.",
            type(filters).__name__,
        )

        service = self._resolve_service(filters, "delete")

        if (
            isinstance(filters, service.model)
            and sa_inspect(filters).persistent
        ):
            try:
                self.session.delete(filters)
            except SQLAlchemyError:
                self.rollback()
                self.logger.exception(
                    "Delete failed while marking object. model=%s.",
                    service.model.__name__,
                )
                return None

            if not self._save("delete"):
                return None

            self.logger.info(
                "Delete finished. model=%s count=1.",
                service.model.__name__,
            )
            return 1

        filter_data = self._filter_data(filters)
        stmt = service.build_delete(filter_data)

        if stmt is None:
            self.logger.warning(
                "Delete rejected. service=%s filters=%r.",
                service.__class__.__name__,
                filters,
            )
            return None

        try:
            result = self.session.execute(stmt)
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception(
                "Delete failed. service=%s filters=%r.",
                service.__class__.__name__,
                filters,
            )
            return None

        if not self._save("delete"):
            return None

        rowcount = int(result.rowcount or 0)
        self.logger.info(
            "Delete finished. model=%s count=%s.",
            service.model.__name__,
            rowcount,
        )
        return rowcount

    def export_to_xlsx(
        self,
        model_names: Sequence[str] | None,
        file_path: str | Path,
    ) -> Path:
        """
        Экспортирует данные выбранных сущностей в XLSX-файл.

        :param model_names: Имена моделей или листов, которые нужно выгрузить. Если
            передано `None`, экспортируются все поддерживаемые сущности.
        :param file_path: Путь, по которому нужно сохранить XLSX-файл.
        :return: Путь к сохраненному XLSX-файлу.
        :raises OrmServiceError: Если не удалось нормализовать имена сущностей или
            получить данные из базы для экспорта.
        """
        self.logger.info(
            "XLSX export started. model_names=%s target=%s.",
            model_names,
            file_path,
        )

        try:
            sheet_keys = normalize_sheet_keys(
                None if model_names is None else list(model_names)
            )
        except ValueError as exc:
            self.logger.error(
                "XLSX export failed: unsupported model names=%s.",
                model_names,
            )
            raise OrmServiceError(str(exc)) from exc

        export_payload = self._export_payload_for_sheet_keys(sheet_keys)
        exported_path = self._import_export_service.export_to_xlsx(
            export_payload,
            file_path,
        )

        self.logger.info(
            "XLSX export finished. sheets=%s target=%s.",
            len(export_payload),
            exported_path,
        )
        return exported_path

    def import_from_xlsx(
        self,
        file_path: str | Path,
        model_names: Sequence[str] | None = None,
    ) -> dict[str, int]:
        """
        Импортирует данные из XLSX-файла в базу данных.

        :param file_path: Путь к XLSX-файлу, который нужно загрузить.
        :param model_names: Имена моделей или листов, которые нужно импортировать. Если
            передано `None`, импортируются все найденные в файле поддерживаемые листы.
        :return: Словарь количества успешно импортированных записей по каждому листу.
        :raises OrmServiceError: Если данные файла нельзя сопоставить сервисам,
            одна из строк не проходит create-схему или сохранение завершается ошибкой.
        """
        self.logger.info(
            "XLSX import started. source=%s model_names=%s.",
            file_path,
            model_names,
        )

        imported_data = self._import_export_service.import_from_xlsx(file_path)

        try:
            allowed_sheet_keys = normalize_sheet_keys(
                None if model_names is None else list(model_names)
            )
        except ValueError as exc:
            self.logger.error(
                "XLSX import failed: unsupported model names=%s.",
                model_names,
            )
            raise OrmServiceError(str(exc)) from exc

        filtered_data = {
            sheet_key: imported_data[sheet_key]
            for sheet_key in allowed_sheet_keys
            if sheet_key in imported_data
        }
        imported_counts: dict[str, int] = {}

        for sheet_key, rows in filtered_data.items():
            service = self._service_from_sheet_key(sheet_key)
            imported_counts[sheet_key] = 0

            for row in rows:
                instance = service.create_instance(row)
                if instance is None:
                    self.logger.error(
                        "XLSX import failed: row rejected. sheet=%s row=%r.",
                        sheet_key,
                        row,
                    )
                    raise OrmServiceError(
                        f"Import row was rejected for sheet {sheet_key}."
                    )

                try:
                    self.session.add(instance)
                except SQLAlchemyError as exc:
                    self.rollback()
                    self.logger.exception(
                        "XLSX import failed while adding object. sheet=%s row=%r.",
                        sheet_key,
                        row,
                    )
                    raise OrmServiceError(
                        f"Failed to add imported object for sheet {sheet_key}."
                    ) from exc

                imported_counts[sheet_key] += 1

        if filtered_data and not self._save("import_xlsx"):
            raise OrmServiceError("Failed to save imported XLSX data.")

        self.logger.info(
            "XLSX import finished. sheets=%s counts=%s.",
            len(imported_counts),
            imported_counts,
        )
        return imported_counts

    def commit(self) -> bool:
        """
        Подтверждает текущую транзакцию SQLAlchemy-сессии.

        :return: `True`, если транзакция успешно подтверждена. `False`, если
            SQLAlchemy вернула ошибку и был выполнен rollback.
        """
        self.logger.info("Commit started.")

        try:
            self.session.commit()
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception("Commit failed.")
            return False

        self.logger.info("Commit finished.")
        return True

    def rollback(self) -> None:
        """
        Откатывает текущую транзакцию SQLAlchemy-сессии.

        :return: `None`. Метод меняет состояние сессии, но не возвращает значение.
        """
        self.logger.info("Rollback started.")
        self.session.rollback()
        self.logger.info("Rollback finished.")

    def close(self) -> None:
        """
        Закрывает текущую SQLAlchemy-сессию.

        :return: `None`. После закрытия сессии экземпляр фасада не должен
            использоваться для новых операций с базой данных.
        """
        self.logger.info("Close started.")
        self.session.close()
        self.logger.info("Close finished.")
