"""
Единый фасад записи XLSX-файлов.

Фасад нужен по той же причине, что и reader: верхние слои должны зависеть
от одного понятного writer-объекта, а не знать, какой именно legacy-exporter
или форматная стратегия используется внутри.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.shared.tabular.payloads import ExportPayload
from app.io_tools.exporting.xlsx.exporter import XlsxExporter


class XlsxTableWriter:
    """
    Записывает подготовленный payload в XLSX-файл.
    """

    def __init__(self, *, exporter: XlsxExporter | None = None) -> None:
        self._exporter = exporter or XlsxExporter()

    def write_workbook(
        self,
        payload: ExportPayload,
        file_path: Path,
    ) -> Path:
        """
        Сохраняет payload в XLSX-файл и возвращает путь к нему.
        """
        return self._exporter.export(payload, file_path)
