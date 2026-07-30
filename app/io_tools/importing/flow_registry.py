"""
Реестр import-flow сценариев.

Реестр заменяет размазанные `if/elif` при выборе режима импорта и делает
маршрутизацию расширяемой: новый формат или новый режим добавляется одной
регистрацией flow, а не изменением нескольких условных цепочек.
"""
from __future__ import annotations

from app.io_tools.importing.flow_contracts import FlowKey, ImportFlow
from app.io_tools.shared.registry import KeyedRegistry
from app.io_tools.shared.xlsx.table_reader import XlsxTableReader


class ImportFlowRegistry:
    """
    Хранит и возвращает зарегистрированные import-flow сценарии.
    """

    def __init__(self) -> None:
        self._registry: KeyedRegistry[FlowKey, ImportFlow] = KeyedRegistry()

    def register(self, key: FlowKey, flow: ImportFlow) -> None:
        self._registry.register(key, flow)

    def get(self, key: FlowKey) -> ImportFlow:
        return self._registry.get(key)

    def keys(self) -> tuple[FlowKey, ...]:
        return self._registry.keys()

    def flows(self) -> tuple[ImportFlow, ...]:
        return self._registry.values()


def build_default_import_flow_registry(
    *,
    table_reader: XlsxTableReader | None = None,
) -> ImportFlowRegistry:
    """
    Создаёт стандартный реестр import-flow сценариев для `io_tools`.
    """
    from app.io_tools.importing.xlsx.flow import DetectTablesFlow, RangeReadFlow
    from app.io_tools.importing.xlsx.smart.flow import SmartXlsxImportFlow
    from app.io_tools.importing.xlsx.standard.flow import StandardXlsxImportFlow
    from app.io_tools.importing.xlsx.strict.flow import StrictXlsxImportFlow

    reader = table_reader or XlsxTableReader()
    registry = ImportFlowRegistry()
    registry.register(
        FlowKey("xlsx", "standard", "return"),
        StandardXlsxImportFlow(table_reader=reader),
    )
    registry.register(
        FlowKey("xlsx", "range", "return"),
        RangeReadFlow(table_reader=reader),
    )
    registry.register(
        FlowKey("xlsx", "detect_tables", "return"),
        DetectTablesFlow(table_reader=reader),
    )
    registry.register(
        FlowKey("xlsx", "smart", "return"),
        SmartXlsxImportFlow(table_reader=reader, detailed=False),
    )
    registry.register(
        FlowKey("xlsx", "smart_detailed", "return"),
        SmartXlsxImportFlow(table_reader=reader, detailed=True),
    )
    registry.register(
        FlowKey("xlsx", "strict", "return"),
        StrictXlsxImportFlow(table_reader=reader),
    )
    return registry
