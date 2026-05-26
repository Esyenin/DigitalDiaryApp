"""
Публичные контракты ядра обработки `io_tools`.

Подпакет `engine` хранит наиболее общие элементы:

1. Контексты операций и их состояние.
2. Pipeline runner.
3. Модели промежуточных и итоговых результатов.
4. Базовые интерфейсы стратегий и шагов.

Этот файл собирает основные сущности ядра в одном месте, чтобы остальные
слои импортировали их явно и без знания внутренней структуры подпакета.
"""
from app.io_tools.engine.messages import OperationMessage
from app.io_tools.engine.operation_context import (
    ExportOperationContext,
    ImportOperationContext,
    ImportOperationState,
)
from app.io_tools.engine.operation_result import TabularImportResult
from app.io_tools.engine.pipeline_runner import PipelineRunner
from app.io_tools.engine.processing_models import (
    DataProcessingResult,
    HeaderBinding,
    ImportProcessingResult,
    NormalizedRow,
    ProcessedRow,
    ResolvedRow,
    StrictImportResult,
)
from app.io_tools.engine.steps.base import BaseImportStep
from app.io_tools.engine.strategy_contracts import ExportStrategy, ImportStrategy

__all__ = [
    "OperationMessage",
    "ImportOperationContext",
    "ImportOperationState",
    "ExportOperationContext",
    "TabularImportResult",
    "PipelineRunner",
    "NormalizedRow",
    "ResolvedRow",
    "ImportProcessingResult",
    "HeaderBinding",
    "ProcessedRow",
    "DataProcessingResult",
    "StrictImportResult",
    "BaseImportStep",
    "ImportStrategy",
    "ExportStrategy",
]
