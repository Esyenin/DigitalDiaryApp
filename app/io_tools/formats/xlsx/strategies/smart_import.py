"""
Стратегии smart-подготовки XLSX-диапазона через use-case слой.
"""
from __future__ import annotations

from app.io_tools.application.import_use_cases import (
    PrepareDetailedSmartImportUseCase,
    PrepareSmartImportUseCase,
)
from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.processing_models import (
    DataProcessingResult,
    ImportProcessingResult,
)


class SmartImportStrategy:
    """
    Выполняет smart-импорт диапазона XLSX.
    """

    def __init__(
        self,
        *,
        use_case: PrepareSmartImportUseCase | None = None,
    ) -> None:
        """
        Создаёт стратегию smart-импорта.

        :param use_case: Use-case подготовки smart-payload-ов.
        """
        self.use_case = use_case or PrepareSmartImportUseCase()

    def execute(self, context: ImportOperationContext) -> ImportProcessingResult:
        """
        Запускает smart-подготовку диапазона XLSX.

        :param context: Контекст операции.
        :return: Результат smart-подготовки.
        """
        return self.use_case.execute(context)


class SmartProcessingStrategy:
    """
    Выполняет подробную smart-обработку диапазона XLSX.
    """

    def __init__(
        self,
        *,
        use_case: PrepareDetailedSmartImportUseCase | None = None,
    ) -> None:
        """
        Создаёт стратегию подробной smart-обработки.

        :param use_case: Use-case подробной smart-обработки.
        """
        self.use_case = use_case or PrepareDetailedSmartImportUseCase()

    def execute(self, context: ImportOperationContext) -> DataProcessingResult:
        """
        Запускает подробную smart-обработку диапазона.

        :param context: Контекст операции.
        :return: Подробный результат обработки.
        """
        return self.use_case.execute(context)
