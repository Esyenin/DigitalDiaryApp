"""
Общие контракты и утилиты подсистемы `io_tools`.

Этот пакет содержит формат-независимые сущности, которыми могут
пользоваться и импорт, и экспорт, и будущие UI-сценарии просмотра
диагностики. Идея пакета простая:

1. Вынести публичные DTO и результаты в одно место.
2. Убрать дублирование диагностических моделей между сценариями.
3. Дать новым слоям архитектуры зависеть от стабильных контрактов,
   а не от legacy-модулей со смешанной ответственностью.
"""

from app.io_tools.shared.diagnostics import Diagnostic, DiagnosticCollector
from app.io_tools.shared.registry import KeyedRegistry
from app.io_tools.shared.requests import ExportRequest, ImportRequest
from app.io_tools.shared.results import (
    ExportResult,
    ImportResult,
    SmartImportDetails,
    StandardWorkbookDetails,
    StrictImportDetails,
)

__all__ = [
    "Diagnostic",
    "DiagnosticCollector",
    "KeyedRegistry",
    "ImportRequest",
    "ExportRequest",
    "ImportResult",
    "ExportResult",
    "SmartImportDetails",
    "StrictImportDetails",
    "StandardWorkbookDetails",
]
