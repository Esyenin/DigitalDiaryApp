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


class Base(DeclarativeBase):
    """
    Абстрактный базовый класс.
    Содержит общие поля (id, даты создания и обновления) и логику именования таблиц.
    """

    # Абстрактность
    __abstract__ = True

    # Базовые столбцы модели
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @declared_attr.directive
    def __tablename__(self) -> str:
        """Автоматическое именование таблиц во множественном числе (добавление 's')."""
        return self.__name__.lower() + 's'

    def __repr__(self) -> str:
        """Автоматическое текстовое представление всех моделей."""
        cols = []
        for col in self.__table__.columns.keys():
            cols.append(f"{col}={getattr(self, col)}")
        return f"<{self.__class__.__name__}({', '.join(cols[:4])})>"
