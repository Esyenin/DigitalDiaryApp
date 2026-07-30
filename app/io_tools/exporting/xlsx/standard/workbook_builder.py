"""
Builder стандартной XLSX-книги.

Builder отделяет сценарий экспорта от технической записи файла. Он знает,
как из готового payload получить `ExportResult`, а writer занимается уже
непосредственно сохранением XLSX на диск.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.shared.diagnostics import Diagnostic
from app.io_tools.shared.results import ExportResult
from app.io_tools.shared.tabular.payloads import ExportPayload
from app.io_tools.shared.xlsx.table_writer import XlsxTableWriter


class StandardWorkbookBuilder:
    """
    Строит итог стандартного XLSX-экспорта.
    """

    def __init__(self, *, table_writer: XlsxTableWriter | None = None) -> None:
        self.table_writer = table_writer or XlsxTableWriter()

    def build(self, payload: ExportPayload, target_path: Path) -> ExportResult:
        """
        Записывает payload в XLSX и формирует результат.
        """
        try:
            exported_path = self.table_writer.write_workbook(payload, target_path)
        except Exception as exc:
            return ExportResult(
                target_path=None,
                diagnostics=[
                    Diagnostic(
                        level="error",
                        code="xlsx.export_failed",
                        message=str(exc),
                        source="standard_export",
                    )
                ],
                meta={},
            )

        return ExportResult(
            target_path=exported_path,
            diagnostics=[],
            meta={"legacy_result": exported_path},
        )
