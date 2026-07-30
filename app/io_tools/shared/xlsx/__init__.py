"""
Общие XLSX-контракты и lazy-совместимость.

Пакет нужен как стабильная точка импорта для новой архитектуры и legacy-кода.
Чтобы не создавать циклические импорты, тяжёлые фасады чтения и записи XLSX
подгружаются только по требованию через ``__getattr__``.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from app.io_tools.shared.xlsx.config import (
    SMART_IMPORT_ENTITY_TYPES,
    STRICT_IMPORT_ENTITY_TYPES,
    XLSX_COLUMNS_BY_SHEET,
    XLSX_REQUIRED_COLUMNS_BY_SHEET,
    XLSX_SHEET_KEY_BY_MODEL_NAME,
    XLSX_SHEETS_ORDER,
    get_known_sheet_names,
    is_smart_import_entity_type,
    is_strict_import_entity_type,
    normalize_sheet_keys,
)

__all__ = [
    "XLSX_SHEETS_ORDER",
    "SMART_IMPORT_ENTITY_TYPES",
    "STRICT_IMPORT_ENTITY_TYPES",
    "XLSX_COLUMNS_BY_SHEET",
    "XLSX_REQUIRED_COLUMNS_BY_SHEET",
    "XLSX_SHEET_KEY_BY_MODEL_NAME",
    "normalize_sheet_keys",
    "get_known_sheet_names",
    "is_smart_import_entity_type",
    "is_strict_import_entity_type",
    "XlsxTableReader",
    "XlsxTableWriter",
]


def __getattr__(name: str) -> Any:
    """
    Лениво отдаёт XLSX-фасады, чтобы пакет не тянул тяжёлые зависимости
    при каждом импорте конфигурации.
    """
    if name == "XlsxTableReader":
        return import_module("app.io_tools.shared.xlsx.table_reader").XlsxTableReader
    if name == "XlsxTableWriter":
        return import_module("app.io_tools.shared.xlsx.table_writer").XlsxTableWriter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
