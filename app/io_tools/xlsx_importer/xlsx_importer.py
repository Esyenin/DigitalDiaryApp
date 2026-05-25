"""
Форматный фасад импорта XLSX в разных режимах.

Класс координирует все XLSX-сценарии, но не содержит внутри тяжёлую
нормализацию или валидацию строк. Его задача:

1. Собрать форматные зависимости.
2. Выбрать нужную стратегию чтения.
3. Создать контекст операции.
4. Вернуть результат подходящего use-case.

Таким образом `XlsxImporter` служит форматным gateway-объектом, а не местом,
где смешаны чтение файла, правила сущностей и прикладная оркестрация.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.io_tools.application.import_use_cases import (
    PrepareDetailedSmartImportUseCase,
    PrepareSmartImportUseCase,
    PrepareStrictImportUseCase,
)
from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.operation_result import TabularImportResult
from app.io_tools.formats.xlsx.readers import (
    SelectedRangeReader,
    StandardWorkbookReader,
    TableRegionFinder,
)
from app.io_tools.formats.xlsx.strategies import (
    SmartImportStrategy,
    SmartProcessingStrategy,
    StandardImportStrategy,
    StrictImportStrategy,
)
from app.io_tools.engine.processing_models import (
    DataProcessingResult,
    ImportProcessingResult,
    StrictImportResult,
)
from app.io_tools.tabular.models import ExtractedTable, TableRegion
from app.io_tools.xlsx_importer.raw_reader import RawWorkbookReader, XlsxRangeReader


logger = logging.getLogger(__name__)


class XlsxImporter:
    """
    Координирует чтение XLSX-файлов в разных режимах.

    Класс больше не хранит внутри всю логику чтения и проверки. Он только
    маршрутизирует вызов в нужную стратегию и сохраняет совместимый API для
    существующего кода приложения.
    """

    def __init__(
        self,
        *,
        raw_workbook_reader: RawWorkbookReader | None = None,
        range_reader: XlsxRangeReader | None = None,
    ) -> None:
        """
        Создаёт фасад импорта XLSX.

        :param raw_workbook_reader: Пользовательский reader поиска таблиц.
        :param range_reader: Пользовательский reader диапазона.
        """
        self.raw_workbook_reader = raw_workbook_reader or RawWorkbookReader()
        self.range_reader = range_reader or XlsxRangeReader()

        self.table_region_finder = TableRegionFinder(
            raw_reader=self.raw_workbook_reader,
        )
        self.selected_range_reader = SelectedRangeReader(
            range_reader=self.range_reader,
        )
        self.standard_workbook_reader = StandardWorkbookReader()
        self.standard_import_strategy = StandardImportStrategy(
            workbook_reader=self.standard_workbook_reader,
        )
        self.smart_import_strategy = SmartImportStrategy(
            use_case=PrepareSmartImportUseCase(
                range_reader=self.selected_range_reader,
            )
        )
        self.smart_processing_strategy = SmartProcessingStrategy(
            use_case=PrepareDetailedSmartImportUseCase(
                range_reader=self.selected_range_reader,
            )
        )
        self.strict_import_strategy = StrictImportStrategy(
            use_case=PrepareStrictImportUseCase(
                range_reader=self.selected_range_reader,
            )
        )

    def read_standard_workbook(
        self,
        file_path: str | Path,
    ) -> TabularImportResult:
        """
        Читает стандартный XLSX-файл приложения с диагностикой.

        :param file_path: Путь к XLSX-файлу.
        :return: Результат чтения книги с данными и ошибками.
        """
        logger.info(
            "XlsxImporter standard workbook read requested. source=%s.",
            file_path,
        )
        context = ImportOperationContext(file_path=Path(file_path))
        result = self.standard_import_strategy.execute(context)
        logger.info(
            "XlsxImporter standard workbook read finished. source=%s sheets_count=%s errors=%s.",
            file_path,
            len(result.data),
            len(result.errors),
        )
        return result

    def import_data(self, file_path: str | Path) -> dict[str, list[dict[str, object]]]:
        """
        Импортирует XLSX-файл стандартного формата приложения.

        Метод сохранён для совместимости с текущим кодом. Внутри он опирается
        на новый reader, который умеет сначала собирать диагностику, а затем
        уже решать, нужно ли останавливать импорт.

        :param file_path: Путь к XLSX-файлу.
        :return: Словарь вида `имя_листа -> список строк`.
        :raises ValueError: Если стандартный XLSX-файл содержит ошибки.
        """
        logger.info("XlsxImporter import started. source=%s.", file_path)
        result = self.read_standard_workbook(file_path)
        if not result.is_valid:
            logger.error(
                "XlsxImporter import failed. source=%s errors=%s.",
                file_path,
                result.errors,
            )
            first_error = next(
                message.text
                for message in result.messages
                if message.level == "error"
            )
            raise ValueError(first_error)

        logger.info(
            "XlsxImporter import finished. source=%s sheets_count=%s.",
            file_path,
            len(result.data),
        )
        return result.data

    def find_table_candidates(
        self,
        file_path: str | Path,
        min_score: float = 0.45,
    ) -> list[TableRegion]:
        """
        Ищет в книге области, похожие на таблицы.

        :param file_path: Путь к XLSX-файлу.
        :param min_score: Нижняя граница оценки похожести.
        :return: Список найденных табличных областей.
        """
        logger.info(
            "XlsxImporter raw table detection started. source=%s min_score=%s.",
            file_path,
            min_score,
        )
        tables = self.table_region_finder.find(
            file_path,
            min_score=min_score,
        )
        logger.info(
            "XlsxImporter raw table detection finished. source=%s tables_count=%s.",
            file_path,
            len(tables),
        )
        return tables

    def read_table_range(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str | None = None,
    ) -> ExtractedTable:
        """
        Читает произвольный диапазон листа как отдельную таблицу.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Ожидаемый тип сущности.
        :return: Извлечённая таблица с диагностикой.
        """
        logger.info(
            "XlsxImporter range read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        table = self.selected_range_reader.read(
            file_path,
            sheet_name,
            cell_range,
            entity_type=entity_type,
        )
        logger.info(
            "XlsxImporter range read finished. sheet=%s range=%s rows=%s warnings=%s errors=%s.",
            table.sheet,
            table.range,
            len(table.rows),
            len(table.warnings),
            len(table.errors),
        )
        return table

    def read_detected_table(
        self,
        file_path: str | Path,
        table_region: TableRegion,
        *,
        entity_type: str | None = None,
    ) -> ExtractedTable:
        """
        Читает ранее найденную табличную область как диапазон Excel.

        :param file_path: Путь к XLSX-файлу.
        :param table_region: Найденная табличная область.
        :param entity_type: Ожидаемый тип сущности.
        :return: Извлечённая таблица вместе с диагностикой.
        """
        logger.info(
            "XlsxImporter detected table read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            table_region.sheet,
            table_region.range,
            entity_type,
        )
        table = self.selected_range_reader.read(
            file_path,
            table_region.sheet,
            table_region.range,
            entity_type=entity_type,
        )
        logger.info(
            "XlsxImporter detected table read finished. sheet=%s range=%s rows=%s warnings=%s errors=%s.",
            table.sheet,
            table.range,
            len(table.rows),
            len(table.warnings),
            len(table.errors),
        )
        return table

    def read_smart_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> ImportProcessingResult:
        """
        Читает диапазон и запускает smart-подготовку таблицы.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Тип smart-сущности.
        :return: Результат smart-подготовки.
        """
        logger.info(
            "XlsxImporter smart read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        context = ImportOperationContext(
            file_path=Path(file_path),
            sheet_name=sheet_name,
            cell_range=cell_range,
            entity_type=entity_type,
        )
        result = self.smart_import_strategy.execute(context)
        logger.info(
            "XlsxImporter smart read finished. entity_type=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.create_payloads),
            len(result.errors),
        )
        return result

    def read_strict_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> StrictImportResult:
        """
        Читает диапазон и запускает strict-подготовку таблицы.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Тип strict-сущности.
        :return: Результат strict-подготовки.
        """
        logger.info(
            "XlsxImporter strict read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        context = ImportOperationContext(
            file_path=Path(file_path),
            sheet_name=sheet_name,
            cell_range=cell_range,
            entity_type=entity_type,
        )
        result = self.strict_import_strategy.execute(context)
        logger.info(
            "XlsxImporter strict read finished. entity_type=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.create_payloads),
            len(result.errors),
        )
        return result

    def process_smart_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> DataProcessingResult:
        """
        Читает диапазон и строит полную картину smart-обработки.

        :param file_path: Путь к XLSX-файлу.
        :param sheet_name: Имя листа.
        :param cell_range: Диапазон Excel.
        :param entity_type: Тип smart-сущности.
        :return: Детальный результат обработки.
        """
        logger.info(
            "XlsxImporter smart processing requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        context = ImportOperationContext(
            file_path=Path(file_path),
            sheet_name=sheet_name,
            cell_range=cell_range,
            entity_type=entity_type,
        )
        result = self.smart_processing_strategy.execute(context)
        logger.info(
            "XlsxImporter smart processing finished. entity_type=%s rows=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.rows),
            len(result.create_payloads),
            len(result.errors),
        )
        return result
