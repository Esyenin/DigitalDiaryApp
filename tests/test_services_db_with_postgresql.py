"""
Тестирование базы данных postgreSQL с использованием pytest.
Проверяет работу с сервисов.
"""
# pylint: disable=redefined-outer-name, import-error
from sqlalchemy import create_engine
from sqlalchemy.sql import Delete, Select
from sqlalchemy.orm import sessionmaker
import pytest

# Импорты моделей и настроек проекта
from app.models.base import Base
from app.models.attendance import Attendance
from app.models.comment import Comment
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.mark import Mark
from app.models.schedule import Schedule
from app.models.schedule_group_link import ScheduleGroupLink
from app.models.student import Student
from app.services.group import GroupService
from config import settings

# Глобальный URL для подключения к тестовой БД
DB_URL = settings.get_db_url()


@pytest.fixture(scope="session")
def engine():
    """Создает движок SQLAlchemy для всей тестовой сессии."""

    # Создание движка и генерация таблиц
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    # Возврат функцией значения
    yield engine


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Создает изолированную сессию для каждого отдельного теста.
    Использует транзакцию с откатом (rollback), чтобы база оставалась чистой.
    """

    # Подключение к базе данных
    connection = engine.connect()
    # Открытие транзакции
    transaction = connection.begin()

    # Открытие конкретной сессии
    session = sessionmaker(bind=connection)()

    # Возврат функцией значения
    yield session

    # Закрытие сессии
    session.close()
    # Откат транзакций
    transaction.rollback()
    # Закрытие подключения
    connection.close()

# --- ТЕСТЫ ---

def test_group_service_db_flow(db_session):
    """Проверка полного цикла: создание и получение из реальной БД."""
    group_service = GroupService()

    # Данные для создания
    my_data1 = {"name": "СМ1-21Б"}
    my_data2 = {"name": "ИУ3-22", "speciality": "24.03.01_Специальность"}
    my_data3 = Group(name="БМТ2-32")

    # Создаем и добавляем
    group1 = group_service.create(my_data1)
    group2 = group_service.create(my_data2)
    group3 = group_service.create(my_data3)

    db_session.add_all([group1, group2, group3])
    db_session.flush()

    # Проверяем получение через запросы сервиса
    db_group1 = db_session.scalar(group_service.get(my_data1))
    db_group2 = db_session.scalar(group_service.get(my_data2))
    db_group3 = db_session.scalar(group_service.get(my_data3))

    assert db_group1.name == "СМ1-21Б"
    assert db_group1.speciality is None
    assert db_group2.speciality == "24.03.01_Специальность"
    assert db_group3.name == "БМТ2-32"
    assert db_group3.speciality is None


@pytest.mark.parametrize("valid_data", [
    {"name": "ИУ3-22"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"name": "ИУ3-21", "speciality": None},
    {"name": "wrong name"},
    {"name": "wrong name", "speciality": "wrong speciality"}
])
def test_group_create_validation_positive(valid_data):
    """Тест корректных данных для создания (должен возвращать Group)."""
    service = GroupService()
    assert type(service.create(valid_data)) is Group
    assert type(service.create(service.create(valid_data))) is Group


@pytest.mark.parametrize("invalid_data", [
    {},
    Group(),
    {"name": None},
    {"name": ""},
    {"name": 123},
    {"speciality": "01.01.01"},
    {"name": "ИУ3-21", "speciality": ""},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_create_validation_negative(invalid_data):
    """Тест некорректных данных для создания (должен возвращать None)."""
    service = GroupService()
    assert service.create(invalid_data) is None


@pytest.mark.parametrize("valid_filter", [
    {},
    Group(),
    {"name": "ИУ3-22"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"speciality": "01.02.03_Тест"},
    {"name": "ИУ3-21", "speciality": None},
    {"name": "wrong name"},
    {"name": "wrong name", "speciality": "wrong speciality"},
    {"speciality": "wrong speciality"}
])
def test_group_get_validation_positive(valid_filter):
    """Тест корректных данных для создания запросов get в бд (должен возвращать Select)."""
    service = GroupService()
    assert type(service.get(valid_filter)) is Select


@pytest.mark.parametrize("invalid_filter", [
    {"name": None},
    {"name": ""},
    {"name": 123},
    {"name": "ИУ3-21", "speciality": ""},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_get_validation_negative(invalid_filter):
    """Тест некорректных данных для создания запросов get в бд (должен возвращать None)."""
    service = GroupService()
    assert service.create(invalid_filter) is None


@pytest.mark.parametrize("valid_update", [
    {"name": "ИУ3-22"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"speciality": "01.02.03_Тест"},
    {"name": "ИУ3-21", "speciality": None},
    {"name": "wrong name"},
    {"name": "wrong name", "speciality": "wrong speciality"},
    {"speciality": "wrong speciality"}
])
def test_group_update_validation_positive(valid_update):
    """Тест корректных данных для создания обновленных экземпляров (должен возвращать Group)."""
    service = GroupService()
    my_group = Group(name="СМ13-11А", speciality="11.22.33_ННаименование")
    assert type(service.update(my_group, valid_update)) is Group


@pytest.mark.parametrize("invalid_update", [
    {},
    Group(),
    {"name": None},
    {"name": ""},
    {"name": 123},
    {"name": "ИУ3-21", "speciality": ""},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_update_validation_negative(invalid_update):
    """Тест некорректных данных для создания обновленных экземпляров (должен возвращать None)."""
    service = GroupService()
    my_group = Group(name="СМ13-11А", speciality="11.22.33_ННаименование")
    assert service.update(my_group, invalid_update) is None


@pytest.mark.parametrize("valid_delete", [
    {"name": "ИУ3-22"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"speciality": "01.02.03_Тест"},
    {"name": "ИУ3-21", "speciality": None},
    {"name": "wrong name"},
    {"name": "wrong name", "speciality": "wrong speciality"},
    {"speciality": "wrong speciality"}
])
def test_group_delete_validation_positive(valid_delete):
    """Тест корректных данных для удаления экземпляров (должен возвращать Delete для словарей и Group для Group)."""
    service = GroupService()
    assert type(service.delete(valid_delete)) is Delete
    for k in valid_delete.keys():
        if k == "name":
            assert type(service.delete(service.create(valid_delete))) is Group


@pytest.mark.parametrize("invalid_delete", [
    {},
    Group(),
    {"name": None},
    {"name": ""},
    {"name": 123},
    {"name": "ИУ3-21", "speciality": ""},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_delete_validation_negative(invalid_delete):
    """ест корректных данных для удаления экземпляров (должен возвращать None)."""
    service = GroupService()
    assert service.delete(invalid_delete) is None
