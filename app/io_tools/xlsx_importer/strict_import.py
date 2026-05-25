"""
Тонкая обёртка над strict-pipeline импорта.
"""
from __future__ import annotations

from app.io_tools.application.import_use_cases import PrepareStrictImportUseCase
from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.processing_models import StrictImportResult
from app.io_tools.tabular.models import ExtractedTable


class StrictImportProcessor:
    """
    Координатор строгой подготовки таблицы к импорту.
    """

    def __init__(self) -> None:
        """
        Создаёт strict-процессор.
        """
        self.use_case = PrepareStrictImportUseCase()

    def process_table(self, extracted_table: ExtractedTable) -> StrictImportResult:
        """
        Выполняет strict-проверку и собирает payload-ы.

        :param extracted_table: Извлечённая таблица.
        :return: Результат strict-импорта.
        """
        context = ImportOperationContext.from_extracted_table(extracted_table)
        return self.use_case.execute(context)
