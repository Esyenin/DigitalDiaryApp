"""
Builder итогового результата smart-импорта.

Builder отделяет форму итогового `ImportResult` от конкретной реализации
processor-а. Благодаря этому можно менять внутренний алгоритм smart-разбора,
не трогая flow, dispatcher и публичный API верхних фасадов.
"""
from __future__ import annotations

from app.io_tools.shared.results import (
    DataProcessingResult,
    ImportProcessingResult,
    ImportResult,
    SmartImportDetails,
)
from app.io_tools.shared.tabular.models import ExtractedTable
from app.io_tools.shared.tabular.schema_registry import TabularSchemaRegistry
from app.io_tools.importing.import_report import ImportReportBuilder


class SmartPayloadBuilder:
    """
    Преобразует результат smart-обработки в единый `ImportResult`.
    """

    def __init__(
        self,
        *,
        schema_registry: TabularSchemaRegistry | None = None,
    ) -> None:
        self.schema_registry = schema_registry or TabularSchemaRegistry()

    def build(
        self,
        table: ExtractedTable,
        processing_result: ImportProcessingResult | DataProcessingResult,
    ) -> ImportResult:
        """
        Строит итоговый результат smart-сценария.
        """
        result = ImportReportBuilder.build_smart_result(table, processing_result)

        if (
            isinstance(processing_result, ImportProcessingResult)
            and isinstance(result.details, SmartImportDetails)
            and not result.details.header_bindings
        ):
            entity_type = table.entity_type
            if entity_type is not None:
                result.details.header_bindings = [
                    self.schema_registry.classify_header(entity_type, header)
                    for header in table.headers
                ]

        return result
