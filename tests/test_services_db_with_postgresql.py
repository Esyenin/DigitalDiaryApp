"""
Тестирование базы данных postgreSQL с использованием pytest.
Проверяет работу сервисов.
"""
# pylint: disable=redefined-outer-name, import-error
from sqlalchemy.sql import Delete, Select
import pytest

# Импорты моделей проекта
from app.models import Attendance, Comment, Group, Lesson, Mark, Schedule, ScheduleGroupLink, Student
from app.schemas.group import GroupCreateSchema
from app.services.group import GroupService

# --- ТЕСТЫ ---

def test_group_service_db_flow(db_session):
    """Проверка полного цикла: создание и получение из реальной БД."""
    group_service = GroupService()

    # Данные для создания
    my_data1 = {"name": "СМ1-21Б"}
    my_data2 = {"name": "ИУ3-22", "speciality": "24.03.01_Специальность"}
    my_data3 = Group(name="БМТ2-32")

    # Создаем и добавляем
    group1 = group_service.create_instance(my_data1)
    group2 = group_service.create_instance(my_data2)
    group3 = group_service.create_instance(my_data3)

    db_session.add_all([group1, group2, group3])
    db_session.flush()

    # Проверяем получение через запросы сервиса
    db_group1 = db_session.scalar(group_service.build_select(my_data1))
    db_group2 = db_session.scalar(group_service.build_select(my_data2))
    db_group3 = db_session.scalar(group_service.build_select(my_data3))

    assert db_group1.name == "СМ1-21Б"
    assert db_group1.speciality is None
    assert db_group2.speciality == "24.03.01_Специальность"
    assert db_group3.name == "БМТ2-32"
    assert db_group3.speciality is None


@pytest.mark.parametrize("valid_data", [
    {"name": "ИУ3-22"},
    {"name": "Группа-1"},
    {"name": "wrong name", "speciality": "wrong speciality"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"name": "ИУ3-21", "speciality": None},
    GroupCreateSchema(name="БМТ2-11А"),
])
def test_group_create_validation_positive(valid_data):
    """Тест корректных данных для создания (должен возвращать Group)."""
    service = GroupService()
    assert type(service.create_instance(valid_data)) is Group
    assert type(service.create_instance(service.create_instance(valid_data))) is Group


@pytest.mark.parametrize("invalid_data", [
    {},
    Group(),
    {"name": None},
    {"name": ""},
    {"name": 123},
    {"speciality": "01.01.01"},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_create_validation_negative(invalid_data):
    """Тест некорректных данных для создания (должен возвращать None)."""
    service = GroupService()
    assert service.create_instance(invalid_data) is None


@pytest.mark.parametrize("valid_filter", [
    {},
    Group(),
    {"name": None},
    {"name": "ИУ3-22"},
    {"name": "wrong name"},
    {"name": "wrong name", "speciality": "wrong speciality"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"speciality": "wrong speciality"},
    {"speciality": "01.02.03_Тест"},
    {"name": "ИУ3-21", "speciality": None},
])
def test_group_get_validation_positive(valid_filter):
    """Тест корректных данных для построения Select-запросов к БД."""
    service = GroupService()
    assert type(service.build_select(valid_filter)) is Select


@pytest.mark.parametrize("invalid_filter", [
    {"name": ""},
    {"speciality": ""},
    {"name": 123},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_get_validation_negative(invalid_filter):
    """Тест некорректных данных для построения Select-запросов к БД."""
    service = GroupService()
    assert service.build_select(invalid_filter) is None


@pytest.mark.parametrize("valid_update", [
    {"name": "ИУ3-22"},
    {"name": "wrong name"},
    {"name": "wrong name", "speciality": "wrong speciality"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"speciality": "wrong speciality"},
    {"speciality": "01.02.03_Тест"},
    {"name": "ИУ3-21", "speciality": None},
])
def test_group_update_validation_positive(valid_update):
    """Тест корректных данных для применения изменений к объекту Group."""
    service = GroupService()
    my_group = Group(name="СМ13-11А", speciality="11.22.33_ННаименование")
    assert type(service.apply_update(my_group, valid_update)) is Group


@pytest.mark.parametrize("invalid_update", [
    {},
    Group(),
    {"name": None},
    {"name": ""},
    {"speciality": ""},
    {"name": 123},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_update_validation_negative(invalid_update):
    """Тест некорректных данных для применения изменений к объекту Group."""
    service = GroupService()
    my_group = Group(name="СМ13-11А", speciality="11.22.33_ННаименование")
    assert service.apply_update(my_group, invalid_update) is None


@pytest.mark.parametrize("valid_delete", [
    {"name": None},
    {"name": "ИУ3-22"},
    {"name": "wrong name"},
    {"name": "wrong name", "speciality": "wrong speciality"},
    {"name": "СМ1-21Б", "speciality": "01.02.03_Наименование"},
    {"speciality": "wrong speciality"},
    {"speciality": "01.02.03_Тест"},
    {"name": "ИУ3-21", "speciality": None},
])
def test_group_delete_validation_positive(valid_delete):
    """Тест корректных данных для построения Delete-запросов к БД."""
    service = GroupService()
    assert type(service.build_delete(valid_delete)) is Delete


@pytest.mark.parametrize("invalid_delete", [
    {},
    Group(),
    {"name": ""},
    {"speciality": ""},
    {"name": 123},
    {"name": "ИУ3-21", "speciality": 123},
    {"unknown_field": "data"},
])
def test_group_delete_validation_negative(invalid_delete):
    """Тест некорректных данных для построения Delete-запросов к БД."""
    service = GroupService()
    assert service.build_delete(invalid_delete) is None
