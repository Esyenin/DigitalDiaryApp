"""
Контракты стратегий импорта и экспорта.
"""
from __future__ import annotations

from typing import Protocol

from app.io_tools.engine.operation_context import (
    ExportOperationContext,
    ImportOperationContext,
)


class ImportStrategy(Protocol):
    """
    Контракт стратегии импорта табличных данных.
    """

    def execute(self, context: ImportOperationContext) -> object:
        """
        Выполняет импорт в выбранном режиме.

        :param context: Контекст операции.
        :return: Объект результата стратегии.
        """


class ExportStrategy(Protocol):
    """
    Контракт стратегии экспорта табличных данных.
    """

    def execute(self, context: ExportOperationContext) -> object:
        """
        Выполняет экспорт в выбранном режиме.

        :param context: Контекст операции.
        :return: Объект результата стратегии.
        """
