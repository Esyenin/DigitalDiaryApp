"""
Публичная поверхность подсистемы `io_tools`.

Активная архитектура пакета теперь состоит только из:
1. `service.py`
2. `shared/`
3. `importing/`
4. `exporting/`

Чтобы сохранить обратную совместимость без сохранения старых файлов, этот
модуль:
1. экспортирует публичные сущности верхнего уровня;
2. регистрирует совместимые alias-модули в `sys.modules`;
3. перенаправляет старые импорты на новые источники данных и сценариев.
"""
from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

from app.io_tools.exporting.dispatcher import ExportDispatcher
from app.io_tools.exporting.flow_registry import ExportFlowKey, ExportFlowRegistry
from app.io_tools.exporting.xlsx.exporter import XlsxExporter
from app.io_tools.importing.dispatcher import ImportDispatcher
from app.io_tools.importing.flow_contracts import FlowCapabilities, FlowKey
from app.io_tools.importing.flow_registry import ImportFlowRegistry
from app.io_tools.importing.import_report import ImportReportBuilder
from app.io_tools.importing.xlsx.importer import XlsxImporter
from app.io_tools.importing.xlsx.smart.row_processor import (
    SmartRowProcessor,
    validation_errors_to_messages,
)
from app.io_tools.importing.xlsx.strict.table_processor import StrictTableProcessor
from app.io_tools.service import ImportExportService
from app.io_tools.shared.diagnostics import Diagnostic, DiagnosticCollector
from app.io_tools.shared.registry import KeyedRegistry
from app.io_tools.shared.requests import ExportRequest, ImportRequest
from app.io_tools.shared.results import (
    DataProcessingResult,
    ExportResult,
    ImportProcessingResult,
    ImportResult,
    OperationMessage,
    SmartImportDetails,
    StandardWorkbookDetails,
    StrictImportDetails,
    StrictImportResult,
    TabularImportResult,
)
from app.io_tools.shared.tabular.models import (
    ExtractedTable,
    HeaderBinding,
    NormalizedRow,
    ProcessedRow,
    ResolvedRow,
    RowProcessingState,
    TableRegion,
)
from app.io_tools.shared.tabular.payloads import ExportPayload, ExportRow, RowValue
from app.io_tools.shared.tabular.schema_registry import (
    CREATE_SCHEMA_BY_ENTITY,
    DIRECT_FIELD_ALIASES,
    FILTER_SCHEMA_BY_ENTITY,
    HeaderClassification,
    REFERENCE_FIELD_ALIASES,
    STRICT_CREATE_SCHEMA_BY_ENTITY,
    TabularSchemaRegistry,
    build_direct_alias_index,
    build_reference_alias_index,
    classify_tabular_headers,
    get_known_fields,
    get_required_fields,
    normalize_tabular_header,
)
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
from app.io_tools.shared.xlsx.table_reader import (
    RawWorkbookReader,
    SelectedRangeReader,
    StandardWorkbookReader,
    TableRegionFinder,
    XlsxRangeReader,
    XlsxTableReader,
    find_tables_in_workbook,
    find_tables_on_sheet,
    print_tables,
    tables_to_dicts,
)


class DataNormalizer:
    """
    Совместимый фасад нормализации строк smart-импорта.
    """

    def __init__(
        self,
        *,
        row_processor: SmartRowProcessor | None = None,
    ) -> None:
        self.row_processor = row_processor or SmartRowProcessor()

    @property
    def row_normalizer(self) -> SmartRowProcessor:
        return self.row_processor

    def normalize_table(self, extracted_table: ExtractedTable) -> list[NormalizedRow]:
        return self.row_processor.normalize_table(extracted_table)

    def normalize_row(
        self,
        entity_type: str,
        raw_row: dict[str, object],
        *,
        source_sheet: str,
        source_range: str,
        source_row_number: int,
    ) -> NormalizedRow:
        return self.row_processor.normalize_row(
            entity_type,
            raw_row,
            source_sheet=source_sheet,
            source_range=source_range,
            source_row_number=source_row_number,
        )

    @staticmethod
    def normalize_header(header: str) -> str:
        return SmartRowProcessor.normalize_header(header)

    def describe_header_binding(
        self,
        entity_type: str,
        header: str,
    ) -> tuple[str, str | None]:
        return self.row_processor.describe_header_binding(entity_type, header)

    @staticmethod
    def _validation_errors_to_messages(exc: object) -> list[str]:
        if hasattr(exc, "errors"):
            return validation_errors_to_messages(exc)  # type: ignore[arg-type]
        return []


class DataResolver:
    """
    Совместимый фасад разрешения ссылок smart-импорта.
    """

    def __init__(
        self,
        *,
        reference_resolvers: dict[str, object] | None = None,
    ) -> None:
        self.row_processor = SmartRowProcessor(
            reference_resolvers=reference_resolvers,  # type: ignore[arg-type]
        )

    @property
    def reference_resolver(self) -> SmartRowProcessor:
        return self.row_processor

    def resolve_rows(self, normalized_rows: list[NormalizedRow]) -> list[ResolvedRow]:
        return self.row_processor.resolve_rows(normalized_rows)

    def resolve_row(self, normalized_row: NormalizedRow) -> ResolvedRow:
        return self.row_processor.resolve_row(normalized_row)


class ImportProcessor:
    """
    Совместимый координатор smart-подготовки payload-ов.
    """

    def __init__(
        self,
        *,
        data_normalizer: DataNormalizer | None = None,
        data_resolver: DataResolver | None = None,
    ) -> None:
        if data_normalizer is not None:
            self.row_processor = data_normalizer.row_processor
            if data_resolver is not None:
                self.row_processor.reference_resolvers = dict(
                    data_resolver.row_processor.reference_resolvers
                )
        else:
            reference_resolvers = None
            if data_resolver is not None:
                reference_resolvers = dict(data_resolver.row_processor.reference_resolvers)
            self.row_processor = SmartRowProcessor(
                reference_resolvers=reference_resolvers,
            )

    def process_table(self, extracted_table: ExtractedTable) -> ImportProcessingResult:
        result = self.row_processor.process(extracted_table, detailed=False)
        assert isinstance(result, ImportProcessingResult)
        return result


class DataProcessor:
    """
    Совместимый координатор подробной smart-обработки таблицы.
    """

    def __init__(
        self,
        *,
        data_normalizer: DataNormalizer | None = None,
        data_resolver: DataResolver | None = None,
        import_processor: object | None = None,
    ) -> None:
        del import_processor
        if data_normalizer is not None:
            self.row_processor = data_normalizer.row_processor
            if data_resolver is not None:
                self.row_processor.reference_resolvers = dict(
                    data_resolver.row_processor.reference_resolvers
                )
        else:
            reference_resolvers = None
            if data_resolver is not None:
                reference_resolvers = dict(data_resolver.row_processor.reference_resolvers)
            self.row_processor = SmartRowProcessor(
                reference_resolvers=reference_resolvers,
            )

    def process_table(self, extracted_table: ExtractedTable) -> DataProcessingResult:
        result = self.row_processor.process(extracted_table, detailed=True)
        assert isinstance(result, DataProcessingResult)
        return result


class StrictImportProcessor:
    """
    Совместимый координатор строгой подготовки таблицы к импорту.
    """

    def __init__(
        self,
        *,
        table_processor: StrictTableProcessor | None = None,
    ) -> None:
        self.table_processor = table_processor or StrictTableProcessor()

    def process_table(self, extracted_table: ExtractedTable) -> StrictImportResult:
        return self.table_processor.process_legacy(extracted_table)


def _register_module(
    module_name: str,
    attributes: dict[str, object],
    *,
    package: bool = False,
) -> ModuleType:
    """
    Регистрирует совместимый alias-модуль в `sys.modules`.
    """
    module = ModuleType(module_name)
    module.__dict__.update(attributes)
    if package:
        module.__path__ = []  # type: ignore[attr-defined]
    sys.modules[module_name] = module
    return module


def _install_compat_aliases() -> None:
    """
    Создаёт alias-модули для старых путей импорта.
    """
    _register_module(
        "app.io_tools.import_export_service",
        {"ImportExportService": ImportExportService},
    )
    _register_module(
        "app.io_tools.xlsx_config",
        {
            "SMART_IMPORT_ENTITY_TYPES": SMART_IMPORT_ENTITY_TYPES,
            "STRICT_IMPORT_ENTITY_TYPES": STRICT_IMPORT_ENTITY_TYPES,
            "XLSX_COLUMNS_BY_SHEET": XLSX_COLUMNS_BY_SHEET,
            "XLSX_REQUIRED_COLUMNS_BY_SHEET": XLSX_REQUIRED_COLUMNS_BY_SHEET,
            "XLSX_SHEET_KEY_BY_MODEL_NAME": XLSX_SHEET_KEY_BY_MODEL_NAME,
            "XLSX_SHEETS_ORDER": XLSX_SHEETS_ORDER,
            "get_known_sheet_names": get_known_sheet_names,
            "is_smart_import_entity_type": is_smart_import_entity_type,
            "is_strict_import_entity_type": is_strict_import_entity_type,
            "normalize_sheet_keys": normalize_sheet_keys,
        },
    )
    _register_module(
        "app.io_tools.xlsx_exporter",
        {
            "XlsxExporter": XlsxExporter,
            "ExportPayload": ExportPayload,
            "ExportRow": ExportRow,
            "RowValue": RowValue,
        },
    )

    _register_module("app.io_tools.xlsx_importer", {}, package=True)
    _register_module(
        "app.io_tools.xlsx_importer.xlsx_importer",
        {"XlsxImporter": XlsxImporter},
    )
    _register_module(
        "app.io_tools.xlsx_importer.data_normalizer",
        {
            "DataNormalizer": DataNormalizer,
            "DataResolver": DataResolver,
            "ImportProcessor": ImportProcessor,
        },
    )
    _register_module(
        "app.io_tools.xlsx_importer.data_processor",
        {"DataProcessor": DataProcessor},
    )
    _register_module(
        "app.io_tools.xlsx_importer.raw_reader",
        {
            "RawWorkbookReader": RawWorkbookReader,
            "XlsxRangeReader": XlsxRangeReader,
            "SelectedRangeReader": SelectedRangeReader,
            "TableRegionFinder": TableRegionFinder,
            "StandardWorkbookReader": StandardWorkbookReader,
            "find_tables_on_sheet": find_tables_on_sheet,
            "find_tables_in_workbook": find_tables_in_workbook,
            "print_tables": print_tables,
            "tables_to_dicts": tables_to_dicts,
        },
    )
    _register_module(
        "app.io_tools.xlsx_importer.strict_import",
        {"StrictImportProcessor": StrictImportProcessor},
    )

    _register_module("app.io_tools.tabular", {}, package=True)
    _register_module(
        "app.io_tools.tabular.models",
        {
            "ExtractedTable": ExtractedTable,
            "TableRegion": TableRegion,
            "RowProcessingState": RowProcessingState,
            "HeaderBinding": HeaderBinding,
            "NormalizedRow": NormalizedRow,
            "ResolvedRow": ResolvedRow,
            "ProcessedRow": ProcessedRow,
        },
    )
    _register_module(
        "app.io_tools.tabular.payloads",
        {
            "ExportPayload": ExportPayload,
            "ExportRow": ExportRow,
            "RowValue": RowValue,
        },
    )
    _register_module(
        "app.io_tools.tabular.field_aliases",
        {
            "DIRECT_FIELD_ALIASES": DIRECT_FIELD_ALIASES,
            "REFERENCE_FIELD_ALIASES": REFERENCE_FIELD_ALIASES,
            "normalize_tabular_header": normalize_tabular_header,
            "build_direct_alias_index": build_direct_alias_index,
            "build_reference_alias_index": build_reference_alias_index,
        },
    )
    _register_module(
        "app.io_tools.tabular.entity_schema_rules",
        {
            "FILTER_SCHEMA_BY_ENTITY": FILTER_SCHEMA_BY_ENTITY,
            "CREATE_SCHEMA_BY_ENTITY": CREATE_SCHEMA_BY_ENTITY,
            "STRICT_CREATE_SCHEMA_BY_ENTITY": STRICT_CREATE_SCHEMA_BY_ENTITY,
        },
    )
    _register_module(
        "app.io_tools.tabular.header_classifier",
        {
            "HeaderClassification": HeaderClassification,
            "classify_tabular_headers": classify_tabular_headers,
        },
    )


_install_compat_aliases()


__all__ = [
    "ImportExportService",
    "ImportRequest",
    "ExportRequest",
    "ImportDispatcher",
    "ExportDispatcher",
    "ImportFlowRegistry",
    "ExportFlowRegistry",
    "FlowKey",
    "ExportFlowKey",
    "FlowCapabilities",
    "Diagnostic",
    "DiagnosticCollector",
    "KeyedRegistry",
    "ImportResult",
    "ExportResult",
    "SmartImportDetails",
    "StrictImportDetails",
    "StandardWorkbookDetails",
    "OperationMessage",
    "TabularImportResult",
    "TableRegion",
    "ExtractedTable",
    "RowProcessingState",
    "HeaderBinding",
    "NormalizedRow",
    "ResolvedRow",
    "ProcessedRow",
    "ImportProcessingResult",
    "DataProcessingResult",
    "StrictImportResult",
    "ExportPayload",
    "ExportRow",
    "RowValue",
    "XLSX_SHEETS_ORDER",
    "XLSX_COLUMNS_BY_SHEET",
    "XLSX_REQUIRED_COLUMNS_BY_SHEET",
    "SMART_IMPORT_ENTITY_TYPES",
    "STRICT_IMPORT_ENTITY_TYPES",
    "normalize_sheet_keys",
    "RawWorkbookReader",
    "XlsxRangeReader",
    "SelectedRangeReader",
    "TableRegionFinder",
    "StandardWorkbookReader",
    "XlsxTableReader",
    "DataNormalizer",
    "DataResolver",
    "ImportProcessor",
    "DataProcessor",
    "StrictImportProcessor",
    "XlsxExporter",
    "XlsxImporter",
    "TabularSchemaRegistry",
]
