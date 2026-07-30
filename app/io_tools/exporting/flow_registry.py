"""
Реестр export-flow сценариев.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.io_tools.shared.registry import KeyedRegistry
from app.io_tools.shared.requests import ExportRequest
from app.io_tools.shared.results import ExportResult
from app.io_tools.shared.xlsx.table_writer import XlsxTableWriter


class ExportFlow(Protocol):
    """
    Контракт одного сценария экспорта.
    """

    name: str

    def run(self, request: ExportRequest) -> ExportResult:
        """
        Выполняет один сценарий экспорта.
        """


@dataclass(frozen=True, slots=True)
class ExportFlowKey:
    """
    Ключ маршрута export-flow сценария.
    """

    format_name: str
    strategy_name: str
    destination_name: str


class ExportFlowRegistry:
    """
    Хранит и возвращает export-flow сценарии.
    """

    def __init__(self) -> None:
        self._registry: KeyedRegistry[ExportFlowKey, ExportFlow] = KeyedRegistry()

    def register(self, key: ExportFlowKey, flow: ExportFlow) -> None:
        self._registry.register(key, flow)

    def get(self, key: ExportFlowKey) -> ExportFlow:
        return self._registry.get(key)

    def keys(self) -> tuple[ExportFlowKey, ...]:
        return self._registry.keys()

    def flows(self) -> tuple[ExportFlow, ...]:
        return self._registry.values()


def build_default_export_flow_registry(
    *,
    table_writer: XlsxTableWriter | None = None,
) -> ExportFlowRegistry:
    """
    Создаёт стандартный реестр export-flow сценариев.
    """
    from app.io_tools.exporting.xlsx.standard.flow import StandardXlsxExportFlow

    writer = table_writer or XlsxTableWriter()
    registry = ExportFlowRegistry()
    registry.register(
        ExportFlowKey("xlsx", "standard", "file"),
        StandardXlsxExportFlow(table_writer=writer),
    )
    return registry
