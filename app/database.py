"""
Реализация архитектуры базы данных для приложения (электронный дневник).
Используется SQLAlchemy 2.0 с декларативным стилем описания моделей.
"""
from datetime import datetime
from sqlalchemy import Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from config import settings


# URL-адрес базы данных
DATABASE_URL = settings.get_db_url()
