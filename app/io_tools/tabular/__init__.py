"""
Общие правила, модели и контракты для табличных данных.

Этот подпакет собирает вещи, которые не должны зависеть от конкретного
формата файла. Здесь лежат:

1. Правила сопоставления сущностей и схем.
2. Алиасы заголовков и функции их нормализации.
3. Общие модели найденных диапазонов и извлечённых таблиц.
4. Типы payload-ов, которые могут использоваться разными экспортёрами.

Именно этот слой должен становиться точкой переиспользования, если рядом с
XLSX позже появятся CSV, TSV или иные табличные форматы.
"""
from app.io_tools.tabular.entity_schema_rules import (
    CREATE_SCHEMA_BY_ENTITY,
    FILTER_SCHEMA_BY_ENTITY,
    STRICT_CREATE_SCHEMA_BY_ENTITY,
    get_known_fields,
    get_required_fields,
)
from app.io_tools.tabular.field_aliases import (
    DIRECT_FIELD_ALIASES,
    REFERENCE_FIELD_ALIASES,
    build_direct_alias_index,
    build_reference_alias_index,
    normalize_tabular_header,
)
from app.io_tools.tabular.header_classifier import (
    HeaderClassification,
    classify_tabular_headers,
)
from app.io_tools.tabular.models import ExtractedTable, TableRegion
from app.io_tools.tabular.payloads import ExportPayload, ExportRow, RowValue

__all__ = [
    "CREATE_SCHEMA_BY_ENTITY",
    "FILTER_SCHEMA_BY_ENTITY",
    "STRICT_CREATE_SCHEMA_BY_ENTITY",
    "get_known_fields",
    "get_required_fields",
    "DIRECT_FIELD_ALIASES",
    "REFERENCE_FIELD_ALIASES",
    "build_direct_alias_index",
    "build_reference_alias_index",
    "normalize_tabular_header",
    "HeaderClassification",
    "classify_tabular_headers",
    "ExtractedTable",
    "TableRegion",
    "RowValue",
    "ExportRow",
    "ExportPayload",
]
