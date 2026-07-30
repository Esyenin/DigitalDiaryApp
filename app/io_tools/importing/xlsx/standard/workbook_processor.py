"""
Processor стандартного XLSX-импорта.

Внутренний reader стандартной книги уже реализован и хорошо покрывает
текущий формат приложения. Поэтому processor здесь занимается не чтением,
а адаптацией результата в новый единый `ImportResult`.
"""
from __future__ import annotations

from app.io_tools.importing.import_report import ImportReportBuilder
from app.io_tools.shared.results import ImportResult, TabularImportResult


class StandardWorkbookProcessor:
    """
    Преобразует результат чтения стандартной XLSX-книги в `ImportResult`.
    """

    def process(self, workbook_result: TabularImportResult) -> ImportResult:
        return ImportReportBuilder.build_standard_result(workbook_result)
