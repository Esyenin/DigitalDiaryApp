"""
Модель базовая для всех моделей проекта
"""
from datetime import datetime

from sqlalchemy import Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

try:
    import inflect
except ImportError:  # pragma: no cover - fallback нужен только без внешней зависимости
    inflect = None


def _pluralize_model_name(name: str) -> str:
    """
    Возвращает имя таблицы во множественном числе.

    Если библиотека `inflect` доступна, используется она.
    Иначе применяется простой fallback, которого достаточно
    для текущих имен моделей проекта.
    """
    if inflect is not None:
        return inflect.engine().plural(name)

    if name.endswith("s"):
        return name

    return f"{name}s"


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
        :returns Возвращает строку с названием.
        """
        return _pluralize_model_name(self.__name__.lower())

    def __repr__(self) -> str:
        """
        Автоматическое текстовое представление всех моделей.
        :returns Возвращает строку с данными модели.
        """
        cols = []
        for col in self.__table__.columns.keys():
            cols.append(f"{col}={getattr(self, col)}")
        return f"<{self.__class__.__name__}({', '.join(cols[:4])})>"
