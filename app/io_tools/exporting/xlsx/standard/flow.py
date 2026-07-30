"""
Flow стандартного XLSX-экспорта.
"""
from __future__ import annotations

from app.io_tools.exporting.flow_registry import ExportFlow
from app.io_tools.exporting.xlsx.standard.workbook_builder import (
    StandardWorkbookBuilder,
)
from app.io_tools.shared.requests import ExportRequest
from app.io_tools.shared.results import ExportResult
from app.io_tools.shared.xlsx.table_writer import XlsxTableWriter


class StandardXlsxExportFlow(ExportFlow):
    """
    Координатор стандартного XLSX-экспорта.
    """

    name = "xlsx.standard_export"

    def __init__(
        self,
        *,
        table_writer: XlsxTableWriter | None = None,
        workbook_builder: StandardWorkbookBuilder | None = None,
    ) -> None:
        writer = table_writer or XlsxTableWriter()
        self.workbook_builder = workbook_builder or StandardWorkbookBuilder(
            table_writer=writer,
        )

    def run(self, request: ExportRequest) -> ExportResult:
        return self.workbook_builder.build(request.payload, request.target_path)
