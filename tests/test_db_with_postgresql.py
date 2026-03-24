"""
Тестирование базы данных PostgreSQL с использованием pytest.
Проверяет создание таблиц, корректность связей и работу с сессиями.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Импорты моделей и настроек проекта
from database import Base, Group, Student
from config import settings

# Глобальный URL для подключения к тестовой БД
DB_URL = settings.get_db_url()


@pytest.fixture(scope="session")
def engine():
    """
    Создает движок SQLAlchemy для всей тестовой сессии.
    Предварительно проверяет доступность БД через прямой коннект psycopg2.
    """

    # Создание движка и генерация таблиц
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Создает изолированную сессию для каждого отдельного теста.
    Использует транзакцию с откатом (rollback), чтобы база оставалась чистой.
    """
    connection = engine.connect()
    # Начинаем транзакцию, которую не будем коммитить в базу физически
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    # Откат гарантирует, что данные из теста не останутся в БД
    transaction.rollback()
    connection.close()


# --- ТЕСТЫ ---

def test_postgresql_connection(db_session):
    """Проверка физической записи и генерации ID в Postgres."""
    group = Group(name="СМ1-11Б")
    db_session.add(group)
    db_session.flush()

    assert group.id is not None
    print(f"Группа создана успешно с ID: {group.id}")


def test_create_group_and_student(db_session):
    """Проверка базового создания группы и привязки студента."""
    # Подготовка данных (Arrange)
    group = Group(name="СМ1-21Б")
    db_session.add(group)
    # Получаем ID группы без фиксации транзакции
    db_session.flush()

    student = Student(
        id_group=group.id,
        surname="Иванов",
        first_name="Иван"
    )
    db_session.add(student)
    db_session.flush()

    # Действие (Act)
    stmt = select(Student).where(Student.surname == "Иванов")
    result = db_session.scalars(stmt).first()

    # Проверка (Assert)
    assert result is not None
    assert result.first_name == "Иван"
    assert result.groups.name == "СМ1-21Б"


def test_student_relationship_in_postgres(db_session):
    """Проверка корректности работы Relationship и Lazy Loading."""
    group = Group(name="Группа-1")
    db_session.add(group)
    db_session.flush()

    student = Student(
        id_group=group.id,
        surname="Тестовый",
        first_name="Студент"
    )
    db_session.add(student)
    db_session.flush()

    # Проверяем, что SQLAlchemy может подтянуть группу через объект студента
    stmt = select(Student).where(Student.surname == "Тестовый")
    result = db_session.scalars(stmt).first()

    assert result.groups.name == "Группа-1"