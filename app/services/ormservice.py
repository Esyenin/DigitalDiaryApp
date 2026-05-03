"""
Общий ORM-сервис проекта.

OrmService владеет сессией SQLAlchemy на уровне сценария работы,
выбирает конкретный сервис сущности и выполняет операции с БД.
"""
from __future__ import annotations
# pylint: disable=too-many-arguments

from collections.abc import Iterable, Mapping
import logging
import re
from typing import Any

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Base
from app.services.attendance import AttendanceService
from app.services.base import BaseService
from app.services.comment import CommentService
from app.services.group import GroupService
from app.services.lesson import LessonService
from app.services.mark import MarkService
from app.services.schedule import ScheduleService
from app.services.schedule_group_links import ScheduleGroupLinkService
from app.services.student import StudentService


Payload = BaseModel | Base | Mapping[str, object]
ServiceTarget = str | type[Base] | Base | BaseService[Any]
logger = logging.getLogger(__name__)


def _to_snake_case(value: str) -> str:
    """
    Переводит имя класса в snake_case.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


class OrmService:
    """
    Верхний сервис для работы с ORM-операциями.

    Класс не заменяет конкретные сервисы. Он координирует их:
    - хранит активную сессию;
    - находит сервис по имени сущности, ORM-классу или ORM-объекту;
    - выполняет create/select/update/delete;
    - логирует отклоненные payload-ы и ошибки транзакций.
    """

    _default_service_classes = (
        GroupService,
        StudentService,
        ScheduleService,
        ScheduleGroupLinkService,
        LessonService,
        AttendanceService,
        MarkService,
        CommentService,
    )

    def __init__(
        self,
        session: Session,
        services: Iterable[BaseService[Any]] | None = None,
        *,
        auto_commit: bool = False,
        close_on_exit: bool = False,
        service_logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.auto_commit = auto_commit
        self.close_on_exit = close_on_exit
        self.logger = service_logger or logger
        self._services_by_name: dict[str, BaseService[Any]] = {}
        self._services_by_model: dict[type[Base], BaseService[Any]] = {}

        for service in services or self._build_default_services():
            self.register(service)

    @classmethod
    def _build_default_services(cls) -> tuple[BaseService[Any], ...]:
        """
        Создает стандартный набор сервисов сущностей.
        """
        return tuple(service_class() for service_class in cls._default_service_classes)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Приводит пользовательский ключ сервиса к единому виду.
        """
        return name.strip().lower().replace("-", "_")

    @classmethod
    def _default_aliases(cls, service: BaseService[Any]) -> set[str]:
        """
        Возвращает естественные имена, по которым можно найти сервис.
        """
        model_name = service.model.__name__
        snake_model_name = _to_snake_case(model_name)
        table_name = getattr(service.model, "__tablename__", "")

        return {
            cls._normalize_name(model_name),
            cls._normalize_name(snake_model_name),
            cls._normalize_name(f"{snake_model_name}s"),
            cls._normalize_name(table_name),
        }

    def register(
        self,
        service: BaseService[Any],
        aliases: Iterable[str] | None = None,
    ) -> None:
        """
        Регистрирует конкретный сервис в общем ORM-сервисе.
        """
        self._services_by_model[service.model] = service
        service_aliases = self._default_aliases(service)
        if aliases is not None:
            service_aliases.update(self._normalize_name(alias) for alias in aliases)

        for alias in service_aliases:
            self._services_by_name[alias] = service

    def service(self, target: ServiceTarget) -> BaseService[Any] | None:
        """
        Возвращает конкретный сервис по имени, модели, объекту или самому сервису.
        """
        if isinstance(target, BaseService):
            return target

        if isinstance(target, str):
            service = self._services_by_name.get(self._normalize_name(target))
            if service is None:
                self.logger.error("Unknown ORM service name: %s.", target)
            return service

        if isinstance(target, type) and issubclass(target, Base):
            service = self._services_by_model.get(target)
            if service is None:
                self.logger.error("Unknown ORM model class: %s.", target.__name__)
            return service

        if isinstance(target, Base):
            return self.service(type(target))

        self.logger.error("Unsupported ORM service target: %r.", target)
        return None

    def __enter__(self) -> "OrmService":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_type is not None:
            self.rollback()
            self.logger.error(
                "OrmService context failed.",
                exc_info=(exc_type, exc_value, traceback),
            )
        elif self.auto_commit:
            self.commit()

        if self.close_on_exit:
            self.close()

        return False

    def _should_commit(self, commit: bool | None) -> bool:
        """
        Определяет, нужно ли завершать операцию commit-ом.
        """
        if commit is None:
            return self.auto_commit

        return commit

    def _finish_write(self, action: str, commit: bool | None) -> bool:
        """
        Завершает write-операцию flush-ем или commit-ом.
        """
        try:
            if self._should_commit(commit):
                self.session.commit()
            else:
                self.session.flush()
            return True
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception("OrmService %s failed while saving changes.", action)
            return False

    def commit(self) -> bool:
        """
        Явно подтверждает транзакцию.
        """
        try:
            self.session.commit()
            self.logger.debug("OrmService session committed.")
            return True
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception("OrmService commit failed.")
            return False

    def rollback(self) -> None:
        """
        Откатывает текущую транзакцию.
        """
        self.session.rollback()
        self.logger.debug("OrmService session rolled back.")

    def close(self) -> None:
        """
        Закрывает текущую сессию.
        """
        self.session.close()
        self.logger.debug("OrmService session closed.")

    def create(
        self,
        target: ServiceTarget,
        data: Payload,
        *,
        commit: bool | None = None,
    ) -> Base | None:
        """
        Создает ORM-объект через конкретный сервис и добавляет его в сессию.
        """
        service = self.service(target)
        if service is None:
            return None

        instance = service.create_instance(data)
        if instance is None:
            self.logger.warning(
                "Create payload rejected by %s.",
                service.__class__.__name__,
            )
            return None

        try:
            self.session.add(instance)
            if not self._finish_write("create", commit):
                return None
            self.logger.info(
                "Created %s with id=%s.",
                service.model.__name__,
                getattr(instance, "id", None),
            )
            return instance
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception("OrmService create failed for %s.", service.model.__name__)
            return None

    def create_many(
        self,
        target: ServiceTarget,
        items: Iterable[Payload],
        *,
        commit: bool | None = None,
    ) -> list[Base] | None:
        """
        Создает несколько ORM-объектов одной сущности.
        """
        service = self.service(target)
        if service is None:
            return None

        instances = []
        for item in items:
            instance = service.create_instance(item)
            if instance is None:
                self.logger.warning(
                    "Create-many payload rejected by %s.",
                    service.__class__.__name__,
                )
                return None
            instances.append(instance)

        try:
            self.session.add_all(instances)
            if not self._finish_write("create_many", commit):
                return None
            self.logger.info(
                "Created %s %s objects.",
                len(instances),
                service.model.__name__,
            )
            return instances
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception(
                "OrmService create_many failed for %s.",
                service.model.__name__,
            )
            return None

    def get_many(
        self,
        target: ServiceTarget,
        filters: Payload | None = None,
    ) -> list[Base] | None:
        """
        Возвращает список объектов по фильтру.
        """
        service = self.service(target)
        if service is None:
            return None

        stmt = service.build_select(filters)
        if stmt is None:
            self.logger.warning(
                "Select payload rejected by %s.",
                service.__class__.__name__,
            )
            return None

        try:
            result = list(self.session.scalars(stmt).all())
            self.logger.debug(
                "Selected %s %s objects.",
                len(result),
                service.model.__name__,
            )
            return result
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception("OrmService select failed for %s.", service.model.__name__)
            return None

    def get_one(
        self,
        target: ServiceTarget,
        filters: Payload | None = None,
    ) -> Base | None:
        """
        Возвращает первый объект по фильтру.
        """
        objects = self.get_many(target, filters)
        if not objects:
            return None

        return objects[0]

    def get(
        self,
        target: ServiceTarget,
        filters: Payload | None = None,
    ) -> list[Base] | None:
        """
        Совместимое короткое имя для get_many.
        """
        return self.get_many(target, filters)

    def update(
        self,
        target: ServiceTarget,
        filters_or_obj: Payload,
        data: Payload,
        *,
        commit: bool | None = None,
    ) -> list[Base] | None:
        """
        Обновляет найденные объекты или один переданный ORM-объект.
        """
        service = self.service(target)
        if service is None:
            return None

        if isinstance(filters_or_obj, service.model):
            objects = [filters_or_obj]
        else:
            objects = self.get_many(service, filters_or_obj)
            if objects is None:
                return None

        updated_objects = []
        for db_obj in objects:
            updated = service.apply_update(db_obj, data)
            if updated is None:
                self.logger.warning(
                    "Update payload rejected by %s.",
                    service.__class__.__name__,
                )
                return None
            updated_objects.append(updated)

        if not self._finish_write("update", commit):
            return None

        self.logger.info(
            "Updated %s %s objects.",
            len(updated_objects),
            service.model.__name__,
        )
        return updated_objects

    def update_one(
        self,
        target: ServiceTarget,
        filters_or_obj: Payload,
        data: Payload,
        *,
        commit: bool | None = None,
    ) -> Base | None:
        """
        Обновляет первый найденный объект.
        """
        updated = self.update(target, filters_or_obj, data, commit=commit)
        if not updated:
            return None

        return updated[0]

    def delete(
        self,
        target: ServiceTarget,
        filters: Payload,
        *,
        commit: bool | None = None,
    ) -> int | None:
        """
        Удаляет объекты по фильтру и возвращает количество затронутых строк.
        """
        service = self.service(target)
        if service is None:
            return None

        stmt = service.build_delete(filters)
        if stmt is None:
            self.logger.warning(
                "Delete payload rejected by %s.",
                service.__class__.__name__,
            )
            return None

        try:
            result = self.session.execute(stmt)
            if not self._finish_write("delete", commit):
                return None
            rowcount = int(result.rowcount or 0)
            self.logger.info(
                "Deleted %s %s objects.",
                rowcount,
                service.model.__name__,
            )
            return rowcount
        except SQLAlchemyError:
            self.rollback()
            self.logger.exception("OrmService delete failed for %s.", service.model.__name__)
            return None
