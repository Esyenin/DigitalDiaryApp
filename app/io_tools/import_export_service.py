"""
Координатор операций импорта и экспорта данных приложения.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.io_tools.xlsx_exporter import ExportPayload, XlsxExporter
from app.io_tools.xlsx_importer import XlsxImporter


logger = logging.getLogger(__name__)


class ImportExportService:
    """
    Верхнеуровневый сервис импорта и экспорта данных.

    Сервис не занимается прямым преобразованием данных в формат Excel. Его
    задача — принимать подготовленные структурированные данные и делегировать
    работу конкретному обработчику формата.
    """

    def __init__(
        self,
        *,
        xlsx_exporter: XlsxExporter | None = None,
        xlsx_importer: XlsxImporter | None = None,
    ) -> None:
        """
        Создает сервис импорта и экспорта.

        :param xlsx_exporter: Пользовательский экземпляр экспортера XLSX.
        :param xlsx_importer: Пользовательский экземпляр импортера XLSX.
        """
        logger.debug("ImportExportService initialization started.")
        self.xlsx_exporter = xlsx_exporter or XlsxExporter()
        self.xlsx_importer = xlsx_importer or XlsxImporter()
        logger.info("ImportExportService initialized successfully.")

    def export_to_xlsx(
        self,
        payload: ExportPayload,
        file_path: str | Path,
    ) -> Path:
        """
        Экспортирует данные в XLSX-файл.

        :param payload: Подготовленные данные экспорта по листам.
        :param file_path: Путь для сохранения XLSX-файла.
        :return: Путь к сохраненному XLSX-файлу.
        """
        logger.info(
            "XLSX export requested. sheets_count=%s target=%s.",
            len(payload),
            file_path,
        )
        exported_path = self.xlsx_exporter.export(payload, file_path)
        logger.info("XLSX export finished. target=%s.", exported_path)
        return exported_path

    def import_from_xlsx(
        self,
        file_path: str | Path,
    ) -> dict[str, list[dict[str, object]]]:
        """
        Импортирует структурированные данные из XLSX-файла.

        :param file_path: Путь к XLSX-файлу.
        :return: Данные по листам в виде словарей строк.
        """
        logger.info("XLSX import requested. source=%s.", file_path)
        imported_data = self.xlsx_importer.import_data(file_path)
        logger.info(
            "XLSX import finished. sheets_count=%s source=%s.",
            len(imported_data),
            file_path,
        )
        return imported_data
