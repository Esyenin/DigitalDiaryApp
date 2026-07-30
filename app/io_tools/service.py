"""
Новый публичный сервис подсистемы `io_tools`.

Сервис остаётся входной точкой для внешнего кода, но теперь опирается
на сценарную архитектуру:

1. `ImportExportService` принимает публичный запрос.
2. Dispatcher выбирает маршрут через реестр flow-ов.
3. Flow координирует reader, processor и builder.
4. Результат при необходимости адаптируется обратно к legacy-API.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.exporting.dispatcher import ExportDispatcher
from app.io_tools.exporting.flow_registry import (
    ExportFlowRegistry,
    build_default_export_flow_registry,
)
from app.io_tools.importing.dispatcher import ImportDispatcher
from app.io_tools.importing.flow_registry import (
    ImportFlowRegistry,
    build_default_import_flow_registry,
)
from app.io_tools.importing.import_report import ImportReportBuilder
from app.io_tools.shared.requests import ExportRequest, ImportRequest
from app.io_tools.shared.tabular.payloads import ExportPayload
from app.io_tools.shared.xlsx.table_reader import XlsxTableReader
from app.io_tools.shared.xlsx.table_writer import XlsxTableWriter


class ImportExportService:
    """
    Предоставляет стабильный публичный API импорта и экспорта.
    """

    def __init__(
        self,
        *,
        import_flow_registry: ImportFlowRegistry | None = None,
        export_flow_registry: ExportFlowRegistry | None = None,
        xlsx_table_reader: XlsxTableReader | None = None,
        xlsx_table_writer: XlsxTableWriter | None = None,
    ) -> None:
        reader = xlsx_table_reader or XlsxTableReader()
        writer = xlsx_table_writer or XlsxTableWriter()
        self.import_flow_registry = import_flow_registry or build_default_import_flow_registry(
            table_reader=reader,
        )
        self.export_flow_registry = export_flow_registry or build_default_export_flow_registry(
            table_writer=writer,
        )
        self.import_dispatcher = ImportDispatcher(self.import_flow_registry)
        self.export_dispatcher = ExportDispatcher(self.export_flow_registry)

    def import_data(self, request: ImportRequest) -> object:
        """
        Выполняет импорт по публичному запросу и возвращает совместимый API-результат.
        """
        result = self.import_dispatcher.execute(request)
        return ImportReportBuilder.unwrap_for_api(result)

    def export_data(self, request: ExportRequest) -> Path:
        """
        Выполняет экспорт по публичному запросу.
        """
        result = self.export_dispatcher.execute(request)
        legacy_result = result.meta.get("legacy_result")
        if isinstance(legacy_result, Path):
            return legacy_result
        if result.target_path is None:
            first_error = next(iter(result.errors), "Export failed.")
            raise ValueError(first_error)
        return result.target_path

    def import_from_xlsx(
        self,
        file_path: str | Path,
    ) -> dict[str, list[dict[str, object]]]:
        """
        Совместимый shortcut стандартного XLSX-импорта.
        """
        result = self.import_data(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="standard",
                destination_name="return",
            )
        )
        if getattr(result, "is_valid", True) is False:
            first_error = next(iter(getattr(result, "errors", [])))
            raise ValueError(first_error)
        return result.data

    def export_to_xlsx(
        self,
        payload: ExportPayload,
        file_path: str | Path,
    ) -> Path:
        """
        Совместимый shortcut стандартного XLSX-экспорта.
        """
        return self.export_data(
            ExportRequest(
                payload=payload,
                target_path=Path(file_path),
                format_name="xlsx",
                strategy_name="standard",
                destination_name="file",
            )
        )
