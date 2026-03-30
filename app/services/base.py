"""
Сервис базовый для всех сервисов проекта.
"""
from typing import Type, TypeVar, Generic, Mapping
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.sql import Delete, Select
from app.models.base import Base


# Указание типа данных как определяемого в конкретном сервисе
T = TypeVar('T', bound=Base)

class BaseService(Generic[T]):
    """
    BaseService — это абстрактный обобщенный (generic) класс,
    реализующий паттерн Repository (с элементами Template Method) для работы с моделями SQLAlchemy.

    Его главная архитектурная особенность — независимость от сессий базы данных (Sessionless).
    Сервис отвечает исключительно за подготовку объектов, формирование SQL-запросов (Select, Delete) и валидацию данных.
    Исполнение этих запросов (работа с БД) делегируется вышестоящему слою.
    """

    def __init__(self, model: Type[T]) -> None:
        """
        Конструктор сервиса. Привязывает сервис к конкретной модели БД и запускает внутреннюю генерацию документации.
        Args:
            model (Type[T]): Класс модели SQLAlchemy, с которой будет работать сервис.
        Returns:
            None
        """
        self.model = model
        self._format_docs()

    # --- Вспомогательные функции класса ---

    def _format_docs(self) -> None:
        """
        Динамически заменяет плейсхолдер [T] в docstrings основных методов (create, get, update, delete)
        на реальное имя модели (self.model.__name__). Это улучшает подсказки в IDE
        при работе с конкретными сервисами-наследниками.
        :return: None
        """
        model_name = self.model.__name__
        for method_name in ['create', 'get', 'update', 'delete']:
            method = getattr(self, method_name)
            if method.__doc__:
                method.__func__.__doc__ = method.__doc__.replace("[T]", model_name)

    @staticmethod
    def _get_data_map(obj: T | Mapping[str, object]) -> Mapping[str, object]:
        """
        Универсальный нормализатор входных данных. Приводит переданный объект к типу словаря (Mapping)
        для удобной валидации и передачи аргументов.
        :param obj: Словарь с данными ИЛИ экземпляр модели [T] SQLAlchemy.
        :return: Если передан словарь — возвращает его без изменений. Если передана модель [T] — извлекает её атрибуты
        через __dict__, отфильтровывая служебные поля SQLAlchemy (начинающиеся с _).
        """
        if isinstance(obj, Mapping):
            return obj
        # Извлекаем данные из атрибутов модели, исключая служебные поля SQLAlchemy
        return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}

    # --- Хуки валидации ---

    def _verify_create(self, obj: Mapping[str, object]) -> bool:
        """
        Проверяет данные перед подготовкой объекта к созданию.
        :param obj: Словарь с данными записи, которые мы хотим добавить в базу данных.
        :return: True, если все данные корректны, False иначе.
        """
        return True

    def _verify_get(self, filters: Mapping[str, object]) -> bool:
        """
        Валидирует параметры фильтрации перед формированием запроса SELECT.
        :param filters: Словарь с фильтрами, которые хотим проверять.
        :return: True, если все данные корректны, False иначе.
        """
        return True

    def _verify_update(self, db_obj: Mapping[str, object], upd_obj: Mapping[str, object]) -> bool:
        """
        Проверяет возможность обновления записи.
        :param db_obj: Словарь записи в базе данных.
        :param upd_obj: Словарь с данными, которые хотим обновить в базе даных.
        :return: True, если все данные корректны, False иначе.
        """
        return True

    def _verify_delete(self, obj: Mapping[str, object]) -> bool:
        """
        Проверяет права или условия перед формированием запроса на удаление.
        :param obj: Словарь с данными, которые хотим удалить.
        :return: True, если все данные корректны, False иначе.
        """
        return True

    # --- CRUD методы ---

    def create(self, obj: T | Mapping[str, object]) -> T | None:
        """
        Подготавливает экземпляр [T] модели для последующего добавления в БД.
        :param obj: Словарь с данными для создания записи ИЛИ уже готовый объект модели [T].
        :return: Экземпляр модели [T], если данные корректные, None иначе.
        """
        verify_data = self._get_data_map(obj)

        if not self._verify_create(verify_data):
            return None

        return self.model(**verify_data) if isinstance(obj, Mapping) else obj


    def get(self, filters: Mapping[str, object] | None = None) -> Select | None:
        """
        Формирует объект SQL-запроса на выборку данных.
        :param filters: (Опционально) Словарь пар "ключ-значение" для фильтрации через WHERE.
        :return: SQL-запроса, если был передан корректный фильтр, None иначе.
        """
        if filters is not None:
            if not self._verify_get(filters):
                return None

        stmt = select(self.model)

        if filters:
            stmt = stmt.filter_by(**filters)

        return stmt

    def update(self, db_obj: T, upd_obj: T | Mapping[str, object]) -> T | None:
        """
        Обновляет атрибуты существующего объекта в базе данных.
        :param db_obj: Существующий объект модели из базы данных.
        :param upd_obj: Словарь с новыми значениями атрибутов или экземпляр модели [T].
        :return: Экземпляр модели [T], если данные корректные, None иначе.
        """
        data = self._get_data_map(upd_obj)
        if not self._verify_update(self._get_data_map(db_obj), data):
            return None

        for key, value in data.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        return db_obj

    def delete(self, db_obj: Mapping[str, object] | T | None = None) -> T | Delete | None:
        """
        Формирует объект SQL-запроса для удаления записи из базы данных.
        :param db_obj: Экземпляр модели ИЛИ словарь с фильтрами. Если в базе данных существует несколько записей,
            удовлетворяющих фильтру, то будут удалены все такие записи.
        :return: Если было передано None или данные оказались некорректные, то вернет None.
            Если был передан экземпляр класса, то метод его же и вернет.
            Если был передан словарь, то метод вернет SQL-запроса на удаление.
        """
        # Если объект не передан вовсе
        if db_obj is None:
            return None

        verify_data = self._get_data_map(db_obj)

        # Проверка прав или условий удаления
        if not self._verify_delete(verify_data):
            return None

        # Если передан словарь — строим SQL запрос удаления
        if isinstance(db_obj, Mapping):
            return sa_delete(self.model).filter_by(**db_obj)

        # Если передан объект — возвращаем его же
        return db_obj
