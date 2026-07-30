"""
Flow strict-импорта XLSX.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.importing.flow_contracts import FlowCapabilities
from app.io_tools.importing.xlsx.strict.table_processor import StrictTableProcessor
from app.io_tools.shared.requests import ImportRequest
from app.io_tools.shared.results import ImportResult
from app.io_tools.shared.xlsx.table_reader import XlsxTableReader


class StrictXlsxImportFlow:
    """
    Координатор strict-импорта XLSX.
    """

    name = "xlsx.strict"
    capabilities = FlowCapabilities(supports_preview=True)

    def __init__(
        self,
        *,
        table_reader: XlsxTableReader | None = None,
        table_processor: StrictTableProcessor | None = None,
    ) -> None:
        self.table_reader = table_reader or XlsxTableReader()
        self.table_processor = table_processor or StrictTableProcessor()

    def run(self, request: ImportRequest) -> ImportResult:
        table = self.table_reader.read_range(
            Path(request.source_path),
            request.sheet_name or "",
            request.cell_range,
            entity_type=request.entity_type,
        )
        return self.table_processor.process(table)
