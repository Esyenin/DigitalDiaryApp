"""
Новый слой сценариев импорта.

Пакет организован вокруг понятия flow: законченного сценария, который
координирует reader, processor и builder. Такой подход делает путь
обработки данных читаемым сверху вниз без лишних промежуточных слоёв.
"""

from app.io_tools.importing.dispatcher import ImportDispatcher
from app.io_tools.importing.flow_contracts import FlowCapabilities, FlowKey, ImportFlow
from app.io_tools.importing.flow_registry import ImportFlowRegistry
from app.io_tools.importing.import_plan import ImportPlan
from app.io_tools.importing.import_report import ImportReportBuilder

__all__ = [
    "ImportFlow",
    "FlowKey",
    "FlowCapabilities",
    "ImportFlowRegistry",
    "ImportDispatcher",
    "ImportPlan",
    "ImportReportBuilder",
]
