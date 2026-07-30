"""
Processor strict-импорта XLSX-таблиц.

Модуль содержит активную strict-логику: проверку заголовков, строгую
валидацию строк и сборку create-payload-ов. Старые strict-модули проекта
используют этот processor как compatibility-обёртку.
"""
from __future__ import annotations

from pydantic import ValidationError

from app.io_tools.importing.import_report import ImportReportBuilder
from app.io_tools.importing.xlsx.smart.row_processor import validation_errors_to_messages
from app.io_tools.shared.results import ImportResult, StrictImportResult
from app.io_tools.shared.tabular.models import ExtractedTable
from app.io_tools.shared.tabular.schema_registry import TabularSchemaRegistry
from app.io_tools.shared.xlsx.config import STRICT_IMPORT_ENTITY_TYPES


class StrictTableProcessor:
    """
    Выполняет строгую проверку и подготовку таблицы к импорту.
    """

    def __init__(
        self,
        *,
        schema_registry: TabularSchemaRegistry | None = None,
    ) -> None:
        self.schema_registry = schema_registry or TabularSchemaRegistry()

    def process(self, table: ExtractedTable) -> ImportResult:
        """
        Выполняет strict-обработку таблицы и возвращает `ImportResult`.
        """
        legacy_result = self.process_legacy(table)
        expected_headers = (
            self.schema_registry.get_strict_headers(table.entity_type or "")
            if table.entity_type
            else []
        )
        return ImportReportBuilder.build_strict_result(
            table,
            legacy_result,
            expected_headers=expected_headers,
        )

    def process_legacy(self, table: ExtractedTable) -> StrictImportResult:
        """
        Выполняет strict-обработку таблицы и возвращает legacy-результат.
        """
        entity_type = self._require_supported_entity_type(table.entity_type)
        expected_headers = self.schema_registry.get_strict_headers(entity_type)
        result = StrictImportResult(
            entity_type=entity_type,
            rows=list(table.rows),
            warnings=[],
            errors=[],
        )

        missing_headers = [
            header for header in expected_headers if header not in table.headers
        ]
        unknown_headers = [
            header for header in table.headers if header not in expected_headers
        ]

        if missing_headers:
            result.errors.append(
                "Missing strict headers: " + ", ".join(missing_headers) + "."
            )
        if unknown_headers:
            result.errors.append(
                "Unknown strict headers: " + ", ".join(unknown_headers) + "."
            )
        if not result.errors and tuple(table.headers) != tuple(expected_headers):
            result.warnings.append(
                "Header order differs from the standard XLSX format."
            )

        create_schema = self.schema_registry.get_strict_create_schema(entity_type)
        if create_schema is None:
            result.errors.append(
                f"No strict create schema is configured for entity type {entity_type!r}."
            )
            return result
        if result.errors:
            return result

        for row_index, row in enumerate(table.rows, start=1):
            strict_row = {
                header: row.get(header)
                for header in expected_headers
            }
            try:
                validated_schema = create_schema.model_validate(strict_row)
            except ValidationError as exc:
                result.errors.extend(
                    f"row {row_index}: {message}"
                    for message in validation_errors_to_messages(exc)
                )
                continue
            result.create_payloads.append(
                validated_schema.model_dump(exclude_unset=True)
            )

        return result

    def _require_supported_entity_type(self, entity_type: str | None) -> str:
        """
        Проверяет, что сущность поддерживается strict-импортом.
        """
        canonical = self.schema_registry.normalize_entity_type(entity_type)
        if canonical is None:
            raise ValueError("Extracted table must contain entity_type.")
        if canonical not in STRICT_IMPORT_ENTITY_TYPES:
            raise ValueError(
                f"Entity type {canonical!r} is not supported for strict import."
            )
        return canonical
