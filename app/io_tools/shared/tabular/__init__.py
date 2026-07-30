"""
Общие модели и правила табличных данных.

Этот пакет отделяет предметные понятия таблиц от конкретного формата
файла. Здесь лежат модели таблиц, профили маппинга, схемные реестры и
общие типы payload-ов, которые могут использовать XLSX, CSV и другие
форматы без копирования контрактов.
"""

from app.io_tools.shared.tabular.mapping_profile import TabularMappingProfile
from app.io_tools.shared.tabular.models import (
    ExtractedTable,
    HeaderBinding,
    RowProcessingState,
    TableRegion,
)
from app.io_tools.shared.tabular.payloads import ExportPayload, ExportRow, RowValue
from app.io_tools.shared.tabular.schema_registry import TabularSchemaRegistry

__all__ = [
    "ExtractedTable",
    "TableRegion",
    "RowProcessingState",
    "HeaderBinding",
    "RowValue",
    "ExportRow",
    "ExportPayload",
    "TabularMappingProfile",
    "TabularSchemaRegistry",
]
