"""
Стратегия strict-подготовки XLSX-диапазона через use-case слой.
"""
from __future__ import annotations

from app.io_tools.application.import_use_cases import PrepareStrictImportUseCase
from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.processing_models import StrictImportResult


class StrictImportStrategy:
    """
    Выполняет strict-импорт диапазона XLSX.
    """

    def __init__(
        self,
        *,
        use_case: PrepareStrictImportUseCase | None = None,
    ) -> None:
        """
        Создаёт стратегию strict-импорта.

        :param use_case: Use-case strict-подготовки.
        """
        self.use_case = use_case or PrepareStrictImportUseCase()

    def execute(self, context: ImportOperationContext) -> StrictImportResult:
        """
        Запускает strict-подготовку диапазона.

        :param context: Контекст операции.
        :return: Результат strict-подготовки.
        """
        return self.use_case.execute(context)
