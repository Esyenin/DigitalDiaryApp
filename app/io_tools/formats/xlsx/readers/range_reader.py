"""
Адаптер чтения выбранного диапазона XLSX.

Модуль нужен как граница между новым форматным деревом и низкоуровневым
legacy-reader, который уже умеет читать Excel-диапазоны. Внешние слои получают
из этого файла только стабильный метод `read(...)` и общую модель
`ExtractedTable`, не зная о деталях старой реализации.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.tabular.models import ExtractedTable
from app.io_tools.xlsx_importer.raw_reader import XlsxRangeReader


class SelectedRangeReader:
    """
    Адаптирует старый reader диапазонов к новому дереву форматов.
    """

    def __init__(self, range_reader: XlsxRangeReader | None = None) -> None:
        """
        Создаёт адаптер чтения диапазонов.

        :param range_reader: Пользовательский reader диапазона.
        """
        self.range_reader = range_reader or XlsxRangeReader()

    def read(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str | None = None,
    ) -> ExtractedTable:
        """
        Считывает выбранный диапазон листа.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Excel-диапазон.
        :param entity_type: Ожидаемый тип сущности.
        :return: Диагностический результат чтения диапазона.
        """
        return self.range_reader.read_range(
            file_path,
            sheet_name,
            cell_range,
            entity_type=entity_type,
        )
