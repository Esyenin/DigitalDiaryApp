"""
Стратегия стандартного экспорта данных в XLSX.

Модуль связывает верхний export-контекст с конкретным XLSX-экспортёром.
Сама стратегия не подготавливает данные и не выбирает destination. Её задача
уже техническая: взять нормализованный payload из контекста и передать его
форматному адаптеру записи.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.engine.operation_context import ExportOperationContext
from app.io_tools.xlsx_exporter import XlsxExporter


class StandardExportStrategy:
    """
    Выполняет стандартный экспорт данных приложения в XLSX.
    """

    def __init__(self, *, xlsx_exporter: XlsxExporter | None = None) -> None:
        """
        Создаёт стратегию стандартного XLSX-экспорта.

        :param xlsx_exporter: Пользовательский экспортёр XLSX.
        """
        self.xlsx_exporter = xlsx_exporter or XlsxExporter()

    def execute(self, context: ExportOperationContext) -> Path:
        """
        Запускает экспорт данных в XLSX.

        :param context: Контекст операции экспорта.
        :return: Путь к сохранённому файлу.
        """
        export_payload = context.export_payload
        if export_payload is None:
            raise ValueError("ExportOperationContext does not contain export_payload.")
        context.result = self.xlsx_exporter.export(
            export_payload,
            context.file_path,
        )
        assert isinstance(context.result, Path)
        return context.result
