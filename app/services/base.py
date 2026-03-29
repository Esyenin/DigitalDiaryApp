"""
Сервис базовый для всех сервисов проекта.
"""
from typing import TypeVar, Generic, Type, List, Mapping
from sqlalchemy.orm import Session
from app.models.base import Base


# Указание типа данных как определяемого в конкретном сервисе
T = TypeVar("T", bound=Base)

class BaseService(Generic[T]):
    """
    Абстрактный базовый класс для всех сервисов.
    Содержит общие поля (модель и сессию, последнюю - если необходимо), методы в соответствие с CRUD.
    """

    def __init__(self, model: Type[T], db: Session | None = None) -> None:
        """
        Конструктор для сервисов.
        Args:
            model: Класс модели SQLAlchemy (например, Group).
            db: Дефолтная сессия SQLAlchemy (может быть None, если передается в методы).
        """
        self.model = model
        self.db = db

    def _get_db(self, db: Session | None = None) -> Session:
        """
        Локальный метод. Определяет приоритетную сессию для выполнения операции.
        Args:
            db: Сессия, переданная напрямую в метод.

        Returns:
            Session: Активная сессия базы данных.

        Raises:
            ValueError: Если сессия не найдена ни в атрибутах класса, ни в аргументах.
        """
        active_db = db or self.db
        if active_db is None:
            raise ValueError("Сессия не установлена ни в классе, ни в аргументе метода.")
        return active_db

    def create(self, obj: T | Mapping[str, object], db: Session | None = None, autocommit: bool = False) -> T:
        """
        Создание записи в базе данных.
        Args:
            obj: Либо готовый экземпляр модели, либо словарь с данными для создания.
            db: Опциональная сессия.
            autocommit: Если True, выполняет commit() и refresh(), иначе — flush().

        Returns:
            T: Созданный экземпляр модели с присвоенным ID.
        """
        session = self._get_db(db)

        if isinstance(obj, Mapping):
            db_obj = self.model(**obj)
        else:
            db_obj = obj

        session.add(db_obj)
        if autocommit:
            session.commit()
            session.refresh(db_obj)
        else:
            session.flush()

        return db_obj

    def get(self, db: Session | None = None, filters: Mapping[str, object] = None) -> T | List[T] | None:
        """
        Получает данные из базы по заданным критериям.

        Args:
            db: Опциональная сессия.
            filters: Словарь фильтров (например, {'name': 'Ivan'}). Если пустой — вернет все записи.

        Returns:
            Один объект (если поиск по id), список объектов или None.
        """
        session = self._get_db(db)

        # Если фильтры не переданы, возвращаем все записи таблицы
        if not filters:
            return session.query(self.model).all()

        # Если в фильтрах есть 'id' и это единственный параметр
        if len(filters) == 1 and "id" in filters:
            return session.get(self.model, filters["id"])

        # В остальных случаях фильтруем по всем ключам из Mapping
        return session.query(self.model).filter_by(**filters).all()

    def update(self, db_obj: int | T, obj_in: Mapping[str, object], db: Session | None = None,
               autocommit: bool = False) -> T | None:
        """
        Обновляет запись в базе данных.
        Args:
            db_obj: ID записи или сам объект модели.
            obj_in: Словарь с обновляемыми полями.
            db: Опциональная сессия.
            autocommit: Режим фиксации транзакции.

        Returns:
            Обновленный объект или None, если запись не найдена.

        Raises:
            AttributeError: Если передан ключ, которого нет в колонках таблицы.
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

    def delete(self, db_obj: Mapping[str, object] | T | None = None, db: Session | None = None,
               autocommit: bool = False) -> bool:
        """
        Удаляет запись из базы данных.

        Если передан словарь (Mapping), удаление произойдет только в том случае,
        если найдена ровно ОДНА запись, соответствующая критериям.

        Args:
            db_obj: Экземпляр модели или словарь с фильтрами.
            db: Опциональная сессия.
            autocommit: Режим фиксации транзакции.

        Returns:
            bool: True если удаление успешно, False в остальных случаях.
        """
        session = self._get_db(db)

        # Если ничего не передали
        if db_obj is None:
            return False

        target_to_delete: T | None = None

        # Если передали словарь (Mapping)
        if isinstance(db_obj, Mapping):
            # Получаем все записи, подходящие под фильтр
            results = session.query(self.model).filter_by(**db_obj).all()

            # Проверяем количество найденных записей
            if len(results) == 1:
                target_to_delete = results[0]
            else:
                return False

        # Если передали готовый объект модели
        elif isinstance(db_obj, self.model):
            target_to_delete = db_obj

        # Если объект не найден или тип данных неверный
        if target_to_delete is None:
            return False

        session.delete(target_to_delete)

        if autocommit:
            session.commit()
        else:
            session.flush()

        return True
