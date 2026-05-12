"""
Координатор операций импорта и экспорта данных приложения.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.io_tools.xlsx_exporter import ExportPayload, XlsxExporter
from app.io_tools.xlsx_importer.data_normalizer import ImportProcessingResult
from app.io_tools.xlsx_importer.data_processor import DataProcessingResult
from app.io_tools.xlsx_importer.raw_reader import ExtractedTable, TableRegion
from app.io_tools.xlsx_importer.strict_import import StrictImportResult
from app.io_tools.xlsx_importer.xlsx_importer import XlsxImporter


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

    def find_xlsx_tables(
        self,
        file_path: str | Path,
        min_score: float = 0.45,
    ) -> list[TableRegion]:
        """
        Ищет нестандартные таблицы в XLSX-файле.

        :param file_path: Путь к XLSX-файлу.
        :param min_score: Минимальный балл похожести на таблицу.
        :return: Список найденных табличных областей.
        """
        logger.info(
            "XLSX table detection requested. source=%s min_score=%s.",
            file_path,
            min_score,
        )
        tables = self.xlsx_importer.find_table_candidates(
            file_path,
            min_score=min_score,
        )
        logger.info(
            "XLSX table detection finished. source=%s tables_count=%s.",
            file_path,
            len(tables),
        )
        logger.debug("XLSX table detection result. tables=%s.", tables)
        return tables

    def read_xlsx_table_range(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str | None = None,
    ) -> ExtractedTable:
        """
        Читает выбранный диапазон XLSX как отдельную таблицу.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Предполагаемый тип данных.
        :return: Извлеченная таблица с диагностикой.
        """
        logger.info(
            "XLSX range read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        table = self.xlsx_importer.read_table_range(
            file_path,
            sheet_name,
            cell_range,
            entity_type=entity_type,
        )
        logger.info(
            "XLSX range read finished. sheet=%s range=%s rows=%s errors=%s.",
            table.sheet,
            table.range,
            len(table.rows),
            len(table.errors),
        )
        if table.warnings:
            logger.debug(
                "XLSX range read warnings. sheet=%s range=%s warnings=%s.",
                table.sheet,
                table.range,
                table.warnings,
            )
        if table.errors:
            logger.warning(
                "XLSX range read returned validation errors. sheet=%s range=%s errors=%s.",
                table.sheet,
                table.range,
                table.errors,
            )
        return table

    def read_smart_xlsx_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> ImportProcessingResult:
        """
        Читает диапазон XLSX и подготавливает его к умному импорту.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Тип smart-сущности.
        :return: Результат умной подготовки таблицы.
        """
        logger.info(
            "Smart XLSX read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        result = self.xlsx_importer.read_smart_table(
            file_path,
            sheet_name,
            cell_range,
            entity_type=entity_type,
        )
        logger.info(
            "Smart XLSX read finished. entity_type=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.create_payloads),
            len(result.errors),
        )
        return result

    def read_strict_xlsx_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> StrictImportResult:
        """
        Читает диапазон XLSX и подготавливает его к строгому импорту.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Тип strict-сущности.
        :return: Результат строгой подготовки таблицы.
        """
        logger.info(
            "Strict XLSX read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        result = self.xlsx_importer.read_strict_table(
            file_path,
            sheet_name,
            cell_range,
            entity_type=entity_type,
        )
        logger.info(
            "Strict XLSX read finished. entity_type=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.create_payloads),
            len(result.errors),
        )
        return result

    def process_smart_xlsx_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> DataProcessingResult:
        """
        Читает диапазон XLSX и возвращает полную картину smart-обработки таблицы.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Тип smart-сущности.
        :return: Результат обработки с картой распознавания и итоговыми
            payload-ами.
        """
        logger.info(
            "Smart XLSX processing requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        result = self.xlsx_importer.process_smart_table(
            file_path,
            sheet_name,
            cell_range,
            entity_type=entity_type,
        )
        logger.info(
            "Smart XLSX processing finished. entity_type=%s rows=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.rows),
            len(result.create_payloads),
            len(result.errors),
        )
        return result
