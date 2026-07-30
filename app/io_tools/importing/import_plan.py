"""
План выбранного import-сценария.

Объект плана небольшой, но делает код dispatcher-а чуть более явным:
из запроса сначала формируется нормализованный маршрут, а уже затем
по нему выбирается нужный flow из реестра.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.io_tools.importing.flow_contracts import FlowKey
from app.io_tools.shared.requests import ImportRequest


@dataclass(frozen=True, slots=True)
class ImportPlan:
    """
    Описывает выбранный маршрут import-flow сценария.
    """

    request: ImportRequest
    key: FlowKey

    @classmethod
    def from_request(cls, request: ImportRequest) -> "ImportPlan":
        """
        Строит план из публичного запроса.
        """
        return cls(
            request=request,
            key=FlowKey(
                format_name=request.format_name,
                strategy_name=request.strategy_name,
                destination_name=request.destination_name,
            ),
        )
