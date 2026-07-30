"""
Контракты новых import-flow сценариев.

Flow — это читаемый координатор законченного сценария импорта. Он не
должен содержать всю бизнес-логику внутри себя: его задача — вызвать
reader, processor и builder в правильном порядке и вернуть `ImportResult`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.io_tools.shared.requests import ImportRequest
from app.io_tools.shared.results import ImportResult


class ImportFlow(Protocol):
    """
    Контракт одного сценария импорта.
    """

    name: str

    def run(self, request: ImportRequest) -> ImportResult:
        """
        Выполняет один сценарий импорта.
        """


@dataclass(frozen=True, slots=True)
class FlowKey:
    """
    Ключ маршрута flow-сценария.
    """

    format_name: str
    strategy_name: str
    destination_name: str = "return"


@dataclass(frozen=True, slots=True)
class FlowCapabilities:
    """
    Явно описывает поддерживаемые возможности flow.
    """

    supports_preview: bool = False
    supports_persist: bool = False
    supports_detailed_result: bool = False
    supports_mapping_profile: bool = False
    supports_table_detection: bool = False
