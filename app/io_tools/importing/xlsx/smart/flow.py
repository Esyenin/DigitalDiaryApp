"""
Flow smart-импорта XLSX.

Основной вход в smart-сценарий читается сверху вниз:
1. прочитать диапазон;
2. обработать строки;
3. собрать итоговый результат.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.importing.flow_contracts import FlowCapabilities
from app.io_tools.importing.xlsx.smart.payload_builder import SmartPayloadBuilder
from app.io_tools.importing.xlsx.smart.row_processor import SmartRowProcessor
from app.io_tools.shared.requests import ImportRequest
from app.io_tools.shared.results import ImportResult
from app.io_tools.shared.xlsx.table_reader import XlsxTableReader


class SmartXlsxImportFlow:
    """
    Координатор smart-импорта XLSX в обычном и детальном режиме.
    """

    capabilities = FlowCapabilities(
        supports_preview=True,
        supports_detailed_result=True,
        supports_mapping_profile=True,
    )

    def __init__(
        self,
        *,
        table_reader: XlsxTableReader | None = None,
        row_processor: SmartRowProcessor | None = None,
        payload_builder: SmartPayloadBuilder | None = None,
        detailed: bool = False,
    ) -> None:
        self.table_reader = table_reader or XlsxTableReader()
        self.row_processor = row_processor or SmartRowProcessor()
        self.payload_builder = payload_builder or SmartPayloadBuilder()
        self.detailed = detailed
        self.name = "xlsx.smart_detailed" if detailed else "xlsx.smart"

    def run(self, request: ImportRequest) -> ImportResult:
        """
        Выполняет smart-сценарий XLSX-импорта.
        """
        table = self.table_reader.read_range(
            Path(request.source_path),
            request.sheet_name or "",
            request.cell_range,
            entity_type=request.entity_type,
        )
        processing_result = self.row_processor.process(
            table,
            detailed=self.detailed,
        )
        return self.payload_builder.build(table, processing_result)
