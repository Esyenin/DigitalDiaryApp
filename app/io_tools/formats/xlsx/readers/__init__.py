"""
Reader-ы XLSX-формата.

Файл собирает форматные адаптеры чтения в одном месте:

1. `SelectedRangeReader` — чтение диапазона.
2. `TableRegionFinder` — поиск табличных областей.
3. `StandardWorkbookReader` — чтение стандартной XLSX-книги приложения.
"""
from app.io_tools.formats.xlsx.readers.range_reader import SelectedRangeReader
from app.io_tools.formats.xlsx.readers.table_region_finder import TableRegionFinder
from app.io_tools.formats.xlsx.readers.workbook_reader import StandardWorkbookReader

__all__ = [
    "SelectedRangeReader",
    "TableRegionFinder",
    "StandardWorkbookReader",
]
