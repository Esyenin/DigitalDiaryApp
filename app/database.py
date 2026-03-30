# database.py
"""
Конфигурация базы данных
"""
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings  # ← Без app.!

# ========== НАСТРОЙКИ БД ==========
DB_URL = settings.get_db_url()

# ========== ДВИЖОК ==========
engine = create_engine(
    DB_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# ========== СЕССИЯ ==========
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

# ========== БАЗОВЫЙ КЛАСС ==========
Base = declarative_base()


# ========== ФУНКЦИИ ==========
def get_session():
    """
    Генератор сессий для работы с БД
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_tables():
    """
    Создать все таблицы в БД
    """
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """
    Удалить все таблицы в БД
    """
    Base.metadata.drop_all(bind=engine)