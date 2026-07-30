"""
Канонический XLSX-экспорт подсистемы `io_tools`.

В модуле живёт реальная логика технической записи XLSX-файла и компактный
фасад для сценарного export-flow слоя. Старый `app.io_tools.xlsx_exporter`
теперь только переэкспортирует `XlsxExporter`.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time
from decimal import Decimal
import logging
from pathlib import Path

from openpyxl import Workbook
from pydantic import BaseModel

from app.io_tools.shared.requests import ExportRequest
from app.io_tools.shared.results import ExportResult
from app.io_tools.shared.tabular.payloads import ExportPayload, ExportRow, RowValue
from app.io_tools.shared.xlsx.config import XLSX_COLUMNS_BY_SHEET, XLSX_SHEETS_ORDER
from app.models import Base


logger = logging.getLogger(__name__)


class XlsxExporter:
    """
    Экспортирует подготовленные данные приложения в XLSX-файл.
    """

    def export(
        self,
        payload: ExportPayload,
        file_path: str | Path,
    ) -> Path:
        """
        Создаёт XLSX-файл из переданного набора листов и строк.
        """
        logger.info(
            "XlsxExporter export started. sheets_count=%s target=%s.",
            len(payload),
            file_path,
        )
        if not payload:
            logger.warning("XlsxExporter export rejected: empty payload.")
            raise ValueError("Для экспорта нужно передать хотя бы один лист.")

        workbook = Workbook()
        first_sheet = True
        ordered_sheet_names = self._resolve_sheet_names(payload)
        logger.debug("XlsxExporter resolved sheet order: %s.", ordered_sheet_names)

        for sheet_name in ordered_sheet_names:
            rows = payload[sheet_name]
            validated_name = self._normalize_sheet_name(sheet_name)
            normalized_rows = self._normalize_rows(rows)
            logger.debug(
                "XlsxExporter prepared sheet=%s rows_count=%s.",
                sheet_name,
                len(normalized_rows),
            )

            worksheet = workbook.active if first_sheet else workbook.create_sheet()
            worksheet.title = validated_name
            self._write_sheet(
                worksheet,
                normalized_rows,
                XLSX_COLUMNS_BY_SHEET.get(sheet_name),
            )
            first_sheet = False

        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(target_path)
        logger.info("XlsxExporter export finished. target=%s.", target_path)
        return target_path

    @staticmethod
    def _resolve_sheet_names(payload: ExportPayload) -> list[str]:
        payload_names = list(payload.keys())
        ordered_names = [
            sheet_name
            for sheet_name in XLSX_SHEETS_ORDER
            if sheet_name in payload
        ]
        ordered_names.extend(
            sheet_name
            for sheet_name in payload_names
            if sheet_name not in ordered_names
        )
        return ordered_names

    @staticmethod
    def _normalize_sheet_name(sheet_name: str) -> str:
        normalized = sheet_name.strip()
        if not normalized:
            raise ValueError("Имя листа Excel не должно быть пустым.")

        invalid_chars = set(r"[]:*?/\\")
        cleaned = "".join(
            character for character in normalized if character not in invalid_chars
        ).strip()
        if not cleaned:
            raise ValueError("Имя листа Excel не должно быть пустым.")

        return cleaned[:31]

    def _normalize_rows(self, rows: Iterable[ExportRow]) -> list[dict[str, RowValue]]:
        return [self._normalize_row(row) for row in rows]

    def _normalize_row(self, row: ExportRow) -> dict[str, RowValue]:
        raw_row: dict[str, object]

        if isinstance(row, BaseModel):
            raw_row = row.model_dump(exclude_unset=False)
        elif isinstance(row, Mapping):
            raw_row = dict(row)
        elif isinstance(row, Base):
            raw_row = {
                key: value
                for key, value in row.__dict__.items()
                if not key.startswith("_")
            }
        else:
            raise ValueError(
                "Строка экспорта должна быть словарём, схемой или ORM-объектом."
            )

        return {
            key: self._normalize_value(value)
            for key, value in raw_row.items()
        }

    @staticmethod
    def _normalize_value(value: object) -> RowValue:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (str, int, float, bool, datetime, date, time)):
            return value
        return str(value)

    def _write_sheet(
        self,
        worksheet: object,
        rows: list[dict[str, RowValue]],
        configured_headers: tuple[str, ...] | None,
    ) -> None:
        headers = self._collect_headers(rows, configured_headers)
        if not headers:
            logger.debug(
                "XlsxExporter skipped empty sheet write. title=%s.",
                worksheet.title,
            )
            return

        worksheet.append(headers)
        for row in rows:
            worksheet.append([row.get(header) for header in headers])

        logger.debug(
            "XlsxExporter wrote sheet=%s headers=%s rows_count=%s.",
            worksheet.title,
            headers,
            len(rows),
        )

    @staticmethod
    def _collect_headers(
        rows: list[dict[str, RowValue]],
        configured_headers: tuple[str, ...] | None,
    ) -> list[str]:
        headers = list(configured_headers or ())
        for row in rows:
            for key in row:
                if key not in headers:
                    headers.append(key)
        return headers


class XlsxExportFacade:
    """
    Предоставляет компактный XLSX-API поверх export-flow сценариев.
    """

    def __init__(
        self,
        *,
        flow_registry: object | None = None,
        table_writer: object | None = None,
    ) -> None:
        from app.io_tools.exporting.dispatcher import ExportDispatcher
        from app.io_tools.exporting.flow_registry import build_default_export_flow_registry

        if table_writer is None:
            from app.io_tools.shared.xlsx.table_writer import XlsxTableWriter

            writer = XlsxTableWriter()
        else:
            writer = table_writer
        self.flow_registry = flow_registry or build_default_export_flow_registry(
            table_writer=writer,
        )
        self.dispatcher = ExportDispatcher(self.flow_registry)

    def export_standard(
        self,
        payload: ExportPayload,
        target_path: str | Path,
    ) -> ExportResult:
        return self.dispatcher.execute(
            ExportRequest(
                payload=payload,
                target_path=Path(target_path),
                format_name="xlsx",
                strategy_name="standard",
                destination_name="file",
            )
        )
