"""
Базовые контракты шагов pipeline импорта.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.io_tools.engine.operation_context import ImportOperationContext


class BaseImportStep(ABC):
    """
    Базовый класс шага pipeline импорта.
    """

    stop_on_error: bool = False

    def should_run(self, context: ImportOperationContext) -> bool:
        """
        Определяет, нужно ли выполнять шаг в текущем контексте.

        :param context: Контекст операции.
        :return: `True`, если шаг должен выполниться.
        """
        del context
        return True

    @abstractmethod
    def run(self, context: ImportOperationContext) -> None:
        """
        Выполняет шаг обработки.

        :param context: Контекст операции.
        :return: `None`.
        """
