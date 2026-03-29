"""
Сервис для управления группами.
Наследует все CRUD методы из BaseService.
"""
from typing import Optional, List, Union, overload
from sqlalchemy.orm import Session
from app.models.group import Group
from app.services.base import BaseService


class GroupService(BaseService[Group]):
    """
    Реализация сервиса.
    Сервис для управления группами.
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        """
        Конструктор для сервисов.
        :param db:
        :return None:
        """
        super().__init__(Group, db)

    def get(self, db: Optional[Session] = None, **kwargs) -> Optional[Group] | List[Group]:
        """
        Универсальный поиск с поддержкой подсказок для имени группы.
        :param db:
        :param kwargs:
        :return:
        """
        return super().get(db=db, **kwargs)