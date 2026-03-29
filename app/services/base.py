"""
Сервис базовый для всех сервисов проекта.
"""
from typing import TypeVar, Generic, Type, Optional, Any, Union
from sqlalchemy.orm import Session
from app.models.base import Base


# Указание типа данных как определяемого в конкретном сервисе
T = TypeVar("T", bound=Base)

class BaseService(Generic[T]):
    """
    Абстрактный базовый класс для всех сервисов.
    Содержит общие поля (модель и сессию, последнюю - если необходимо), методы в соответствие с CRUD.
    """
    def __init__(self, model: Type[T], db: Optional[Session] = None):
        """
        Конструктор для сервисов.
        :param model:
        :param db:
        """
        self.model = model
        self.db = db

    def _get_db(self, db: Optional[Session] = None) -> Session:
        """
        Локальный метод для определения сессии связи с базой данных. Вернет тот, что был задан по умолчанию для объекта
        класса, или тот, что указали в параметрах (последний в приоритете). Иначе выводит ошибку.
        :param db:
        :return Session:
        """
        active_db = db or self.db
        if active_db is None:
            raise ValueError("Сессия не установлена ни в классе, ни в аргументе метода.")
        return active_db

    def create(self, obj: T, db: Optional[Session] = None, autocommit: bool = False) -> T:
        """
        Создание записи в базе данных.
        :param obj:
        :param db:
        :param autocommit:
        :return T:
        """
        session = self._get_db(db)
        session.add(obj)
        if autocommit:
            session.commit()
            session.refresh(obj)
        else:
            session.flush()
        return obj

    def get(self, db: Optional[Session] = None, **kwargs) -> Any:
        """
        Получение записи из базы данных.
        :param db:
        :param kwargs:
        :return Any:
        """
        session = self._get_db(db)
        if len(kwargs) == 1 and "id" in kwargs:
            return session.query(self.model).filter(self.model.id == kwargs["id"]).first()
        return session.query(self.model).filter_by(**kwargs).all()

    def update(self, db_obj: Union[int, T], obj_in: dict[str, Any], db: Optional[Session] = None,
               autocommit: bool = False) -> Optional[T]:
        """
        Обновляет запись в базе данных.
        :param db_obj:
        :param obj_in:
        :param db:
        :return Optional[T]:
        """
        session = self._get_db(db)

        if isinstance(db_obj, int):
            db_obj = session.get(self.model, db_obj)

        if not db_obj:
            return None

        # Проверяем все поля на наличие в бд
        for field in obj_in:
            if not hasattr(db_obj, field):
                raise AttributeError(
                    f"Ошибка валидации: Поле '{field}' отсутствует в модели {self.model.__name__}. "
                    "Обновление прервано."
                )

        # Обновление полей в бд
        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        if autocommit:
            session.commit()
            session.refresh(db_obj)
        else:
            session.flush()
        return db_obj

    def delete(self, db_obj: Union[int, T], db: Optional[Session] = None, autocommit: bool = False) -> bool:
        """
        Удаление объекта по ID или по самому экземпляру.
        :param db_obj:
        :param db:
        :param autocommit:
        :return bool:
        """
        session = self._get_db(db)

        if isinstance(db_obj, int):
            db_obj = session.get(self.model, db_obj)

        if db_obj:
            session.delete(db_obj)
            if autocommit:
                session.commit()
            else:
                session.flush()
            return True
        return False
