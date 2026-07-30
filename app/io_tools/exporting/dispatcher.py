"""
Dispatcher нового слоя экспорта.
"""
from __future__ import annotations

import logging

from app.io_tools.exporting.flow_registry import ExportFlowKey, ExportFlowRegistry
from app.io_tools.shared.requests import ExportRequest
from app.io_tools.shared.results import ExportResult


logger = logging.getLogger(__name__)


class ExportDispatcher:
    """
    Выбирает export-flow по формату, стратегии и destination.
    """

    def __init__(self, flow_registry: ExportFlowRegistry) -> None:
        self.flow_registry = flow_registry

    def execute(self, request: ExportRequest) -> ExportResult:
        key = ExportFlowKey(
            request.format_name,
            request.strategy_name,
            request.destination_name,
        )
        try:
            flow = self.flow_registry.get(key)
        except KeyError as exc:
            raise ValueError(
                "Unsupported export route: "
                f"format={request.format_name!r}, "
                f"strategy={request.strategy_name!r}, "
                f"destination={request.destination_name!r}."
            ) from exc

        logger.info(
            "Export requested. format=%s strategy=%s target=%s destination=%s.",
            request.format_name,
            request.strategy_name,
            request.target_path,
            request.destination_name,
        )
        result = flow.run(request)
        if result.warnings:
            logger.debug("%s returned warnings: %s.", flow.name, result.warnings)
        if result.errors:
            logger.warning("%s returned errors: %s.", flow.name, result.errors)
        return result
