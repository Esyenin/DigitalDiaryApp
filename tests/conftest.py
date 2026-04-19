"""
Общие фикстуры для тестов с PostgreSQL.
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
    Создает движок SQLAlchemy для всей тестовой сессии.
    """
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Создает изолированную сессию для каждого отдельного теста.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
