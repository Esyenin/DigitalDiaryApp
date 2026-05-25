"""
Публичная поверхность подсистемы `io_tools`.

Подсистема отвечает за работу с табличными форматами данных и объединяет
несколько уровней архитектуры:

1. `application` — API-запросы, dispatcher-ы и use-case'ы.
2. `engine` — контексты, pipeline и промежуточные модели.
3. `tabular` — общие правила и контракты для таблиц.
4. `formats/xlsx` — конкретные XLSX-адаптеры.

Этот файл собирает основные точки входа и типы, которые могут понадобиться
внешнему коду, не заставляя его знать внутреннюю структуру подпакетов.
"""
from app.io_tools.application import (
    DeliverPreparedPayloadsUseCase,
    ExportRequest,
    ImportRequest,
    PrepareDetailedSmartImportUseCase,
    PrepareSmartImportUseCase,
    PrepareStrictImportUseCase,
)
from app.io_tools.engine import OperationMessage, TabularImportResult
from app.io_tools.engine.processing_models import (
    DataProcessingResult,
    HeaderBinding,
    ImportProcessingResult,
    NormalizedRow,
    ProcessedRow,
    ResolvedRow,
    StrictImportResult,
)
from app.io_tools.import_export_service import ImportExportService
from app.io_tools.tabular import ExportPayload
from app.io_tools.tabular.models import ExtractedTable, TableRegion
from app.io_tools.xlsx_config import (
    XLSX_COLUMNS_BY_SHEET,
    XLSX_REQUIRED_COLUMNS_BY_SHEET,
    XLSX_SHEETS_ORDER,
)
from app.io_tools.xlsx_exporter import XlsxExporter
from app.io_tools.xlsx_importer.data_normalizer import (
    DataNormalizer,
    DataResolver,
    ImportProcessor,
)
from app.io_tools.xlsx_importer.data_processor import DataProcessor
from app.io_tools.xlsx_importer.raw_reader import RawWorkbookReader, XlsxRangeReader
from app.io_tools.xlsx_importer.strict_import import StrictImportProcessor
from app.io_tools.xlsx_importer.xlsx_importer import XlsxImporter

__all__ = [
    "ImportExportService",
    "PrepareSmartImportUseCase",
    "PrepareDetailedSmartImportUseCase",
    "PrepareStrictImportUseCase",
    "DeliverPreparedPayloadsUseCase",
    "ImportRequest",
    "ExportRequest",
    "OperationMessage",
    "TabularImportResult",
    "XLSX_SHEETS_ORDER",
    "XLSX_COLUMNS_BY_SHEET",
    "XLSX_REQUIRED_COLUMNS_BY_SHEET",
    "TableRegion",
    "ExtractedTable",
    "ExportPayload",
    "NormalizedRow",
    "ResolvedRow",
    "ImportProcessingResult",
    "HeaderBinding",
    "ProcessedRow",
    "DataProcessingResult",
    "StrictImportResult",
    "RawWorkbookReader",
    "XlsxRangeReader",
    "DataNormalizer",
    "DataResolver",
    "ImportProcessor",
    "DataProcessor",
    "StrictImportProcessor",
    "XlsxExporter",
    "XlsxImporter",
]
