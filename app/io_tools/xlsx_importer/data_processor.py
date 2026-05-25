"""
Тонкие обёртки над подробной smart-обработкой таблиц.
"""
from __future__ import annotations

from app.io_tools.application.import_use_cases import (
    PrepareDetailedSmartImportUseCase,
)
from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.processing_models import DataProcessingResult
from app.io_tools.tabular.models import ExtractedTable
from app.io_tools.xlsx_importer.data_normalizer import (
    DataNormalizer,
    DataResolver,
)


class DataProcessor:
    """
    Координатор подробной smart-обработки таблицы.
    """

    def __init__(
        self,
        *,
        data_normalizer: DataNormalizer | None = None,
        data_resolver: DataResolver | None = None,
        import_processor: object | None = None,
    ) -> None:
        """
        Создаёт обработчик подробной smart-обработки.

        :param data_normalizer: Пользовательский нормализатор.
        :param data_resolver: Пользовательский резолвер ссылок.
        :param import_processor: Параметр сохранён как игнорируемый адаптер.
        """
        del import_processor
        self.data_normalizer = data_normalizer or DataNormalizer()
        self.data_resolver = data_resolver or DataResolver()
        self.use_case = PrepareDetailedSmartImportUseCase(
            row_normalizer=self.data_normalizer.row_normalizer,
            reference_resolver=self.data_resolver.reference_resolver,
        )

    def process_table(self, extracted_table: ExtractedTable) -> DataProcessingResult:
        """
        Строит полную трассировку smart-обработки таблицы.

        :param extracted_table: Извлечённая таблица.
        :return: Подробный результат обработки.
        """
        context = ImportOperationContext.from_extracted_table(extracted_table)
        return self.use_case.execute(context)
