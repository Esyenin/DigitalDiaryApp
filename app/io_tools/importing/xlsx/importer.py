"""
Новый фасад XLSX-импорта.

Фасад сохраняет существующий публичный API, но внутри уже работает через
новый `FlowRegistry` и `ImportDispatcher`. Старые методы остаются
адаптерами и возвращают прежние объекты, чтобы не ломать внешний код.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.io_tools.importing.dispatcher import ImportDispatcher
from app.io_tools.importing.flow_registry import (
    ImportFlowRegistry,
    build_default_import_flow_registry,
)
from app.io_tools.importing.import_report import ImportReportBuilder
from app.io_tools.shared.requests import ImportRequest
from app.io_tools.shared.results import ImportResult
from app.io_tools.shared.tabular.models import ExtractedTable, TableRegion
from app.io_tools.shared.xlsx.table_reader import XlsxTableReader


logger = logging.getLogger(__name__)


class XlsxImporter:
    """
    Предоставляет совместимый XLSX-API поверх нового flow-слоя.
    """

    def __init__(
        self,
        *,
        flow_registry: ImportFlowRegistry | None = None,
        table_reader: XlsxTableReader | None = None,
    ) -> None:
        self.table_reader = table_reader or XlsxTableReader()
        self.flow_registry = flow_registry or build_default_import_flow_registry(
            table_reader=self.table_reader,
        )
        self.dispatcher = ImportDispatcher(self.flow_registry)

    def _run(self, request: ImportRequest) -> ImportResult:
        return self.dispatcher.execute(request)

    def read_standard_workbook(self, file_path: str | Path) -> object:
        logger.info(
            "XlsxImporter standard workbook read requested. source=%s.",
            file_path,
        )
        result = self._run(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="standard",
                destination_name="return",
            )
        )
        legacy_result = ImportReportBuilder.unwrap_for_api(result)
        logger.info(
            "XlsxImporter standard workbook read finished. source=%s errors=%s.",
            file_path,
            len(getattr(legacy_result, "errors", [])),
        )
        return legacy_result

    def import_data(self, file_path: str | Path) -> dict[str, list[dict[str, object]]]:
        logger.info("XlsxImporter import started. source=%s.", file_path)
        result = self.read_standard_workbook(file_path)
        if getattr(result, "is_valid", True) is False:
            logger.error(
                "XlsxImporter import failed. source=%s errors=%s.",
                file_path,
                getattr(result, "errors", []),
            )
            first_error = next(iter(getattr(result, "errors", [])))
            raise ValueError(first_error)
        logger.info("XlsxImporter import finished. source=%s.", file_path)
        return result.data

    def detect_tables(
        self,
        file_path: str | Path,
        min_score: float = 0.45,
    ) -> list[TableRegion]:
        logger.info(
            "XlsxImporter raw table detection started. source=%s min_score=%s.",
            file_path,
            min_score,
        )
        result = self._run(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="detect_tables",
                destination_name="return",
                min_score=min_score,
            )
        )
        tables = ImportReportBuilder.unwrap_for_api(result)
        logger.info(
            "XlsxImporter raw table detection finished. source=%s tables_count=%s.",
            file_path,
            len(tables),
        )
        return tables

    def find_table_candidates(
        self,
        file_path: str | Path,
        min_score: float = 0.45,
    ) -> list[TableRegion]:
        return self.detect_tables(file_path, min_score=min_score)

    def read_range(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str | None = None,
    ) -> ExtractedTable:
        logger.info(
            "XlsxImporter range read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        result = self._run(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="range",
                destination_name="return",
                sheet_name=sheet_name,
                cell_range=cell_range,
                entity_type=entity_type,
            )
        )
        table = ImportReportBuilder.unwrap_for_api(result)
        logger.info(
            "XlsxImporter range read finished. sheet=%s range=%s rows=%s warnings=%s errors=%s.",
            table.sheet,
            table.range,
            len(table.rows),
            len(table.warnings),
            len(table.errors),
        )
        return table

    def read_table_range(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str | None = None,
    ) -> ExtractedTable:
        return self.read_range(
            file_path,
            sheet_name,
            cell_range,
            entity_type=entity_type,
        )

    def read_detected_table(
        self,
        file_path: str | Path,
        table_region: TableRegion,
        *,
        entity_type: str | None = None,
    ) -> ExtractedTable:
        logger.info(
            "XlsxImporter detected table read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            table_region.sheet,
            table_region.range,
            entity_type,
        )
        table = self.table_reader.read_range(
            Path(file_path),
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
    ) -> object:
        logger.info(
            "XlsxImporter smart read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        result = self._run(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="smart",
                destination_name="return",
                sheet_name=sheet_name,
                cell_range=cell_range,
                entity_type=entity_type,
            )
        )
        legacy_result = ImportReportBuilder.unwrap_for_api(result)
        logger.info(
            "XlsxImporter smart read finished. entity_type=%s payloads=%s errors=%s.",
            getattr(legacy_result, "entity_type", None),
            len(getattr(legacy_result, "create_payloads", [])),
            len(getattr(legacy_result, "errors", [])),
        )
        return legacy_result

    def process_smart_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> object:
        logger.info(
            "XlsxImporter smart processing requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        result = self._run(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="smart_detailed",
                destination_name="return",
                sheet_name=sheet_name,
                cell_range=cell_range,
                entity_type=entity_type,
            )
        )
        legacy_result = ImportReportBuilder.unwrap_for_api(result)
        logger.info(
            "XlsxImporter smart processing finished. entity_type=%s rows=%s payloads=%s errors=%s.",
            getattr(legacy_result, "entity_type", None),
            len(getattr(legacy_result, "rows", [])),
            len(getattr(legacy_result, "create_payloads", [])),
            len(getattr(legacy_result, "errors", [])),
        )
        return legacy_result

    def read_strict_table(
        self,
        file_path: str | Path,
        sheet_name: str,
        cell_range: str,
        *,
        entity_type: str,
    ) -> object:
        logger.info(
            "XlsxImporter strict read requested. source=%s sheet=%s range=%s entity_type=%s.",
            file_path,
            sheet_name,
            cell_range,
            entity_type,
        )
        result = self._run(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="strict",
                destination_name="return",
                sheet_name=sheet_name,
                cell_range=cell_range,
                entity_type=entity_type,
            )
        )
        legacy_result = ImportReportBuilder.unwrap_for_api(result)
        logger.info(
            "XlsxImporter strict read finished. entity_type=%s payloads=%s errors=%s.",
            getattr(legacy_result, "entity_type", None),
            len(getattr(legacy_result, "create_payloads", [])),
            len(getattr(legacy_result, "errors", [])),
        )
        return legacy_result
