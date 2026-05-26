"""
Стратегии XLSX-операций.

Стратегия в рамках `io_tools` определяет, какой прикладной сценарий нужно
запустить для одного и того же формата. Для XLSX это прежде всего:

1. Стандартный импорт книги приложения.
2. Smart-подготовка пользовательского диапазона.
3. Strict-подготовка диапазона.
4. Стандартный экспорт в XLSX.
"""
from app.io_tools.formats.xlsx.strategies.smart_import import (
    SmartImportStrategy,
    SmartProcessingStrategy,
)
from app.io_tools.formats.xlsx.strategies.standard_export import (
    StandardExportStrategy,
)
from app.io_tools.formats.xlsx.strategies.standard_import import (
    StandardImportStrategy,
)
from app.io_tools.formats.xlsx.strategies.strict_import import (
    StrictImportStrategy,
)

__all__ = [
    "SmartImportStrategy",
    "SmartProcessingStrategy",
    "StandardExportStrategy",
    "StandardImportStrategy",
    "StrictImportStrategy",
]
