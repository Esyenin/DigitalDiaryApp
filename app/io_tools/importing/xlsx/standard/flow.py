"""
Flow стандартного XLSX-импорта.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.io_tools.importing.flow_contracts import FlowCapabilities
from app.io_tools.importing.xlsx.standard.workbook_processor import (
    StandardWorkbookProcessor,
)
from app.io_tools.shared.requests import ImportRequest
from app.io_tools.shared.results import ImportResult
from app.io_tools.shared.xlsx.table_reader import XlsxTableReader


logger = logging.getLogger(__name__)


class StandardXlsxImportFlow:
    """
    Координатор импорта стандартной XLSX-книги приложения.
    """

    name = "xlsx.standard"
    capabilities = FlowCapabilities(supports_preview=True)

    def __init__(
        self,
        *,
        table_reader: XlsxTableReader | None = None,
        workbook_processor: StandardWorkbookProcessor | None = None,
    ) -> None:
        self.table_reader = table_reader or XlsxTableReader()
        self.workbook_processor = workbook_processor or StandardWorkbookProcessor()

    def run(self, request: ImportRequest) -> ImportResult:
        logger.info(
            "XlsxImporter standard workbook read requested. source=%s.",
            request.source_path,
        )
        workbook_result = self.table_reader.read_workbook(Path(request.source_path))
        result = self.workbook_processor.process(workbook_result)
        legacy_result = result.legacy_result
        logger.info(
            "XlsxImporter standard workbook read finished. source=%s sheets_count=%s errors=%s.",
            request.source_path,
            len(getattr(legacy_result, "data", {})),
            len(getattr(legacy_result, "errors", [])),
        )
        return result
