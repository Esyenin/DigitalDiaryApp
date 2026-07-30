"""
Построение новых `ImportResult` и адаптация к старому API.

Новый flow-слой должен возвращать единый `ImportResult`, но публичный API
проекта уже использует legacy-результаты: `TabularImportResult`,
`ImportProcessingResult`, `DataProcessingResult`, `StrictImportResult`,
`ExtractedTable` и даже `list[TableRegion]`. Этот модуль соединяет оба мира.
"""
from __future__ import annotations

from typing import Iterable

from app.io_tools.shared.diagnostics import Diagnostic
from app.io_tools.shared.results import (
    DataProcessingResult,
    ImportProcessingResult,
    ImportResult,
    OperationMessage,
    SmartImportDetails,
    StandardWorkbookDetails,
    TabularImportResult,
    StrictImportResult,
    StrictImportDetails,
)
from app.io_tools.shared.tabular.models import ExtractedTable, TableRegion


class ImportReportBuilder:
    """
    Собирает новый `ImportResult` и умеет отдать legacy-результат обратно.
    """

    @staticmethod
    def _diagnostics_from_texts(
        warnings: Iterable[str],
        errors: Iterable[str],
        *,
        source: str,
        sheet_name: str | None = None,
        cell_range: str | None = None,
    ) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        seen: set[tuple[str, str]] = set()

        for warning in warnings:
            key = ("warning", warning)
            if key in seen:
                continue
            seen.add(key)
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    code="legacy.warning",
                    message=warning,
                    sheet_name=sheet_name,
                    cell_range=cell_range,
                    source=source,
                )
            )

        for error in errors:
            key = ("error", error)
            if key in seen:
                continue
            seen.add(key)
            diagnostics.append(
                Diagnostic(
                    level="error",
                    code="legacy.error",
                    message=error,
                    sheet_name=sheet_name,
                    cell_range=cell_range,
                    source=source,
                )
            )

        return diagnostics

    @staticmethod
    def build_standard_result(legacy_result: TabularImportResult) -> ImportResult:
        """
        Строит новый результат из legacy-результата стандартного импорта.
        """
        diagnostics = [
            Diagnostic.from_operation_message(
                message,
                code="standard.workbook",
                source="standard_workbook",
            )
            for message in legacy_result.messages
        ]
        details = StandardWorkbookDetails(
            sheets=list(legacy_result.data.keys()),
            rows_by_sheet={
                sheet_name: len(rows)
                for sheet_name, rows in legacy_result.data.items()
            },
        )
        return ImportResult(
            entity_type=None,
            payloads=[],
            diagnostics=diagnostics,
            rows=[],
            details=details,
            meta={
                "legacy_result": legacy_result,
                "data": legacy_result.data,
            },
        )

    @classmethod
    def build_range_result(cls, table: ExtractedTable) -> ImportResult:
        """
        Строит новый результат для простого чтения диапазона.
        """
        diagnostics = list(table.diagnostics) or cls._diagnostics_from_texts(
            table.warnings,
            table.errors,
            source="range_read",
            sheet_name=table.sheet,
            cell_range=table.range,
        )
        return ImportResult(
            entity_type=table.entity_type,
            payloads=[],
            diagnostics=diagnostics,
            rows=list(table.rows),
            details=table,
            meta={"legacy_result": table},
        )

    @staticmethod
    def build_detect_tables_result(tables: list[TableRegion]) -> ImportResult:
        """
        Строит результат сценария поиска таблиц.
        """
        return ImportResult(
            entity_type=None,
            payloads=[],
            diagnostics=[],
            rows=[],
            details=tables,
            meta={"legacy_result": tables},
        )

    @classmethod
    def build_smart_result(
        cls,
        extracted_table: ExtractedTable,
        legacy_result: ImportProcessingResult | DataProcessingResult,
    ) -> ImportResult:
        """
        Строит новый результат smart-импорта из legacy-объекта.
        """
        if isinstance(legacy_result, DataProcessingResult):
            diagnostics = cls._diagnostics_from_texts(
                legacy_result.warnings,
                legacy_result.errors,
                source="smart_detailed",
                sheet_name=extracted_table.sheet,
                cell_range=extracted_table.range,
            )
            details = SmartImportDetails(
                header_bindings=list(legacy_result.header_bindings),
                rows=list(legacy_result.rows),
            )
            rows = list(legacy_result.rows)
        else:
            diagnostics = cls._diagnostics_from_texts(
                list(extracted_table.warnings) + list(legacy_result.warnings),
                list(extracted_table.errors) + list(legacy_result.errors),
                source="smart",
                sheet_name=extracted_table.sheet,
                cell_range=extracted_table.range,
            )
            details = SmartImportDetails(
                header_bindings=[],
                rows=[],
            )
            rows = []

        return ImportResult(
            entity_type=legacy_result.entity_type,
            payloads=list(legacy_result.create_payloads),
            diagnostics=diagnostics,
            rows=rows,
            details=details,
            meta={
                "legacy_result": legacy_result,
                "source_table": extracted_table,
            },
        )

    @classmethod
    def build_strict_result(
        cls,
        extracted_table: ExtractedTable,
        legacy_result: StrictImportResult,
        *,
        expected_headers: list[str],
    ) -> ImportResult:
        """
        Строит новый результат strict-импорта.
        """
        diagnostics = cls._diagnostics_from_texts(
            legacy_result.warnings,
            legacy_result.errors,
            source="strict",
            sheet_name=extracted_table.sheet,
            cell_range=extracted_table.range,
        )
        details = StrictImportDetails(
            expected_headers=expected_headers,
            actual_headers=list(extracted_table.headers),
        )
        return ImportResult(
            entity_type=legacy_result.entity_type,
            payloads=list(legacy_result.create_payloads),
            diagnostics=diagnostics,
            rows=list(legacy_result.rows),
            details=details,
            meta={
                "legacy_result": legacy_result,
                "source_table": extracted_table,
            },
        )

    @staticmethod
    def unwrap_for_api(result: ImportResult) -> object:
        """
        Возвращает legacy-результат, если он есть, иначе сам `ImportResult`.
        """
        return result.legacy_result if result.legacy_result is not None else result
