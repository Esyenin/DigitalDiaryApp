"""
Общие фикстуры тестов.

Файл содержит общие настройки тестов базы данных:
- подключение к тестовой БД;
- создание SQLAlchemy engine;
- создание тестовой сессии с откатом транзакции.

Импорт `Base` из `app.models` загружает все модули моделей
и регистрирует таблицы в `Base.metadata`.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.models import Base
from config import settings


DB_URL = settings.get_db_url()


@pytest.fixture(scope="session")
def engine():
    """
    Создает SQLAlchemy engine для тестовой сессии.
    """
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Создает изолированную сессию для одного теста.

    После завершения теста транзакция откатывается.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
