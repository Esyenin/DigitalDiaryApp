"""
Application-слой подсистемы `io_tools`.

Здесь собраны два типа элементов:

1. Публичные API-контракты и dispatcher-объекты.
2. Прикладные use-case'ы подготовки импорта.

Именно этот слой связывает внешний сервисный API с внутренним engine, не
позволяя верхним фасадам напрямую оркестрировать шаги обработки.
"""
from app.io_tools.application.api_dispatchers import (
    DiagnosticsLogger,
    ExportDispatcher,
    ImportDispatcher,
)
from app.io_tools.application.api_requests import ExportRequest, ImportRequest
from app.io_tools.application.import_use_cases import (
    DeliverPreparedPayloadsUseCase,
    PrepareDetailedSmartImportUseCase,
    PrepareSmartImportUseCase,
    PrepareStrictImportUseCase,
)

__all__ = [
    "DiagnosticsLogger",
    "ExportDispatcher",
    "ImportDispatcher",
    "ImportRequest",
    "ExportRequest",
    "DeliverPreparedPayloadsUseCase",
    "PrepareDetailedSmartImportUseCase",
    "PrepareSmartImportUseCase",
    "PrepareStrictImportUseCase",
]
