"""
Стратегия стандартного импорта XLSX внутреннего формата приложения.
"""
from __future__ import annotations

from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.operation_result import TabularImportResult
from app.io_tools.engine.pipeline_runner import PipelineRunner
from app.io_tools.formats.xlsx.readers.workbook_reader import StandardWorkbookReader


class _ReadStandardWorkbookStep:
    """
    Шаг pipeline стандартного чтения XLSX-книги.
    """

    def __init__(self, workbook_reader: StandardWorkbookReader) -> None:
        """
        Сохраняет reader стандартной книги.

        :param workbook_reader: Reader стандартного XLSX-формата.
        """
        self.workbook_reader = workbook_reader

    def run(self, context: ImportOperationContext) -> None:
        """
        Считывает книгу и сохраняет результат в контекст.

        :param context: Контекст операции.
        :return: `None`.
        """
        context.result = self.workbook_reader.read(context.file_path)


class StandardImportStrategy:
    """
    Выполняет стандартный импорт XLSX через единый pipeline.
    """

    def __init__(
        self,
        *,
        workbook_reader: StandardWorkbookReader | None = None,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        """
        Создаёт стратегию стандартного импорта.

        :param workbook_reader: Reader стандартного XLSX.
        :param pipeline_runner: Исполнитель шагов pipeline.
        """
        self.workbook_reader = workbook_reader or StandardWorkbookReader()
        self.pipeline_runner = pipeline_runner or PipelineRunner()

    def execute(self, context: ImportOperationContext) -> TabularImportResult:
        """
        Запускает стандартный импорт книги.

        :param context: Контекст операции.
        :return: Результат чтения книги.
        """
        self.pipeline_runner.run(
            context,
            [_ReadStandardWorkbookStep(self.workbook_reader)],
        )
        assert isinstance(context.result, TabularImportResult)
        return context.result
