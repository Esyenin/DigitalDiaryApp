"""
Адаптер поиска табличных областей в XLSX-книге.

Файл изолирует внешний форматный слой от низкоуровневого детектора областей.
На выход наружу он отдаёт только общую модель `TableRegion`, чтобы более
высокие слои не зависели от структуры legacy-reader напрямую.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.tabular.models import TableRegion
from app.io_tools.xlsx_importer.raw_reader import RawWorkbookReader


class TableRegionFinder:
    """
    Адаптирует старый детектор таблиц к новому дереву форматов.
    """

    def __init__(self, raw_reader: RawWorkbookReader | None = None) -> None:
        """
        Создаёт адаптер поиска табличных областей.

        :param raw_reader: Пользовательский детектор таблиц.
        """
        self.raw_reader = raw_reader or RawWorkbookReader()

    def find(
        self,
        file_path: str | Path,
        min_score: float = 0.45,
    ) -> list[TableRegion]:
        """
        Ищет табличные области во всей книге.

        :param file_path: Путь к XLSX-файлу.
        :param min_score: Нижняя граница оценки похожести на таблицу.
        :return: Список найденных областей.
        """
        return self.raw_reader.find_tables_in_workbook(
            file_path,
            min_score=min_score,
        )
