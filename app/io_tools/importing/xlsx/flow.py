"""
Простые XLSX-flow сценарии без дополнительной постобработки.

Сюда вынесены режимы, которым не нужен отдельный processor: чтение одного
диапазона и поиск табличных областей. Они всё равно оформлены как flow-ы,
чтобы dispatcher работал с единым абстрактным интерфейсом.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.importing.flow_contracts import FlowCapabilities
from app.io_tools.importing.import_report import ImportReportBuilder
from app.io_tools.shared.requests import ImportRequest
from app.io_tools.shared.results import ImportResult
from app.io_tools.shared.xlsx.table_reader import XlsxTableReader


class RangeReadFlow:
    """
    Сценарий чтения одного XLSX-диапазона.
    """

    name = "xlsx.range"
    capabilities = FlowCapabilities(supports_preview=True)

    def __init__(self, *, table_reader: XlsxTableReader | None = None) -> None:
        self.table_reader = table_reader or XlsxTableReader()

    def run(self, request: ImportRequest) -> ImportResult:
        table = self.table_reader.read_range(
            Path(request.source_path),
            request.sheet_name or "",
            request.cell_range,
            entity_type=request.entity_type,
        )
        return ImportReportBuilder.build_range_result(table)


class DetectTablesFlow:
    """
    Сценарий поиска табличных областей в XLSX-книге.
    """

    name = "xlsx.detect_tables"
    capabilities = FlowCapabilities(
        supports_preview=True,
        supports_table_detection=True,
    )

    def __init__(self, *, table_reader: XlsxTableReader | None = None) -> None:
        self.table_reader = table_reader or XlsxTableReader()

    def run(self, request: ImportRequest) -> ImportResult:
        tables = self.table_reader.find_tables(
            Path(request.source_path),
            min_score=request.min_score or 0.45,
        )
        return ImportReportBuilder.build_detect_tables_result(tables)
