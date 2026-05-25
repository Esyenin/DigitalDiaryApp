"""
Маленькие шаги strict-импорта и их сборка результатов.
"""
from __future__ import annotations

from pydantic import ValidationError

from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.processing_models import StrictImportResult
from app.io_tools.engine.steps.base import BaseImportStep
from app.io_tools.engine.steps.smart_steps import validation_errors_to_messages
from app.io_tools.tabular.entity_schema_rules import STRICT_CREATE_SCHEMA_BY_ENTITY
from app.io_tools.xlsx_config import (
    XLSX_COLUMNS_BY_SHEET,
    is_strict_import_entity_type,
)


class StrictImportAssembler:
    """
    Собирает итог strict-импорта из шагов pipeline.
    """

    def build_result(self, context: ImportOperationContext) -> StrictImportResult:
        extracted_table = context.state.extracted_table
        if extracted_table is None or extracted_table.entity_type is None:
            raise ValueError("Import context does not contain a valid extracted_table.")

        entity_type = extracted_table.entity_type
        result = StrictImportResult(
            entity_type=entity_type,
            rows=list(extracted_table.rows),
            warnings=list(context.state.strict_header_warnings),
            errors=list(context.state.strict_header_errors),
        )

        create_schema = STRICT_CREATE_SCHEMA_BY_ENTITY.get(entity_type)
        if create_schema is None:
            result.errors.append(
                f"No strict create schema is configured for entity type {entity_type!r}."
            )
            return result

        if result.errors:
            return result

        expected_headers = XLSX_COLUMNS_BY_SHEET[entity_type]
        for row_index, row in enumerate(extracted_table.rows, start=1):
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


class ValidateStrictHeadersStep(BaseImportStep):
    """
    Шаг строгой проверки состава и порядка заголовков.
    """

    stop_on_error = False

    def run(self, context: ImportOperationContext) -> None:
        extracted_table = context.state.extracted_table
        if extracted_table is None:
            raise ValueError("Import context does not contain extracted_table.")
        if extracted_table.entity_type is None:
            raise ValueError("Extracted table must contain entity_type.")

        entity_type = extracted_table.entity_type
        if not is_strict_import_entity_type(entity_type):
            raise ValueError(
                f"Entity type {entity_type!r} is not supported for strict import."
            )

        expected_headers = XLSX_COLUMNS_BY_SHEET[entity_type]
        actual_headers = extracted_table.headers

        missing_headers = tuple(
            header for header in expected_headers if header not in actual_headers
        )
        unknown_headers = tuple(
            header for header in actual_headers if header not in expected_headers
        )

        context.state.strict_header_errors = []
        context.state.strict_header_warnings = []

        if missing_headers:
            context.state.strict_header_errors.append(
                "Missing strict headers: " + ", ".join(missing_headers) + "."
            )
        if unknown_headers:
            context.state.strict_header_errors.append(
                "Unknown strict headers: " + ", ".join(unknown_headers) + "."
            )
        if (
            not context.state.strict_header_errors
            and tuple(actual_headers) != tuple(expected_headers)
        ):
            context.state.strict_header_warnings.append(
                "Header order differs from the standard XLSX format."
            )


class BuildStrictImportResultStep(BaseImportStep):
    """
    Шаг сборки итогового strict-результата.
    """

    def __init__(self, assembler: StrictImportAssembler) -> None:
        self.assembler = assembler

    def run(self, context: ImportOperationContext) -> None:
        context.state.strict_result = self.assembler.build_result(context)
        context.result = context.state.strict_result
