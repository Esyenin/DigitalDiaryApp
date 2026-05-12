"""
Инструменты импорта данных из XLSX.

Подпакет объединяет два сценария работы с Excel-файлами:

1. Стандартный импорт
   Используется для внутренних таблиц приложения, где листы, порядок колонок
   и обязательные поля заранее известны.
2. Импорт произвольного диапазона
   Используется для чтения таблиц, которые находятся в любом месте листа и
   требуют либо умной нормализации, либо строгой проверки формата.

Основные публичные точки входа:

- `XlsxImporter` — фасад чтения XLSX;
- `RawWorkbookReader` — поиск табличных областей в книге;
- `XlsxRangeReader` — чтение конкретного диапазона;
- `DataNormalizer`, `DataResolver`, `ImportProcessor` — умная подготовка
  внешних таблиц;
- `StrictImportProcessor` — строгая подготовка таблиц внутреннего формата.
"""
from app.io_tools.xlsx_importer.data_normalizer import (
    DataNormalizer,
    DataResolver,
    ImportProcessingResult,
    ImportProcessor,
    NormalizedRow,
    ResolvedRow,
)
from app.io_tools.xlsx_importer.data_processor import (
    DataProcessingResult,
    DataProcessor,
    HeaderBinding,
    ProcessedRow,
)
from app.io_tools.xlsx_importer.strict_import import (
    StrictImportProcessor,
    StrictImportResult,
)
from app.io_tools.xlsx_importer.raw_reader import (
    ExtractedTable,
    RawWorkbookReader,
    TableRegion,
    XlsxRangeReader,
)
from app.io_tools.xlsx_importer.xlsx_importer import XlsxImporter

__all__ = [
    "TableRegion",
    "ExtractedTable",
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
    "XlsxImporter",
]
