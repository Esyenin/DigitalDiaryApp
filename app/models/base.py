"""
Модель базовая для всех моделей проекта
"""
import inflect
from datetime import datetime
from sqlalchemy import Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """
    Абстрактный базовый класс моделей.
    Содержит общие поля (id, даты создания и обновления), логику именования таблиц.
    """

    # Абстрактность модели
    __abstract__ = True

    # Базовые столбцы модели
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @declared_attr.directive
    def __tablename__(self) -> str:
        """
        Автоматическое именование таблиц во множественном числе.
        С учетом правильного образования слова.
        """
        return inflect.engine().plural(self.__name__.lower())

    def __repr__(self) -> str:
        """Автоматическое текстовое представление всех моделей."""
        cols = []
        for col in self.__table__.columns.keys():
            cols.append(f"{col}={getattr(self, col)}")
        return f"<{self.__class__.__name__}({', '.join(cols[:4])})>"
