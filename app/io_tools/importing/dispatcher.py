"""
Dispatcher нового слоя импорта.

Dispatcher отвечает только за выбор маршрута и запуск нужного flow. Он
не читает XLSX сам и не знает внутреннюю бизнес-логику режимов smart,
strict или standard. Такой слой делает сервис тонким и расширяемым.
"""
from __future__ import annotations

import logging

from app.io_tools.importing.flow_registry import ImportFlowRegistry
from app.io_tools.importing.import_plan import ImportPlan
from app.io_tools.shared.requests import ImportRequest
from app.io_tools.shared.results import ImportResult


logger = logging.getLogger(__name__)


class ImportDispatcher:
    """
    Выбирает import-flow по формату, стратегии и destination.
    """

    def __init__(self, flow_registry: ImportFlowRegistry) -> None:
        self.flow_registry = flow_registry

    def execute(self, request: ImportRequest) -> ImportResult:
        """
        Выполняет импорт по описанию публичного запроса.
        """
        plan = ImportPlan.from_request(request)
        try:
            flow = self.flow_registry.get(plan.key)
        except KeyError as exc:
            raise ValueError(
                "Unsupported import route: "
                f"format={request.format_name!r}, "
                f"strategy={request.strategy_name!r}, "
                f"destination={request.destination_name!r}."
            ) from exc

        logger.info(
            "Import requested. format=%s strategy=%s source=%s destination=%s.",
            request.format_name,
            request.strategy_name,
            request.source_path,
            request.destination_name,
        )
        result = flow.run(request)
        operation_name = self._operation_name(request)
        if result.warnings:
            logger.debug(
                "%s warnings: %s.",
                operation_name,
                result.warnings,
            )
        if result.errors:
            logger.warning(
                "%s returned validation errors: %s.",
                operation_name,
                result.errors,
            )
        return result

    @staticmethod
    def _operation_name(request: ImportRequest) -> str:
        """
        Возвращает человекочитаемое имя операции для совместимых логов.
        """
        if request.format_name == "xlsx" and request.strategy_name == "standard":
            return "Standard XLSX read"
        if request.format_name == "xlsx" and request.strategy_name == "range":
            return "XLSX range read"
        if request.format_name == "xlsx" and request.strategy_name == "smart":
            return "Smart XLSX read"
        if request.format_name == "xlsx" and request.strategy_name == "smart_detailed":
            return "Smart XLSX processing"
        if request.format_name == "xlsx" and request.strategy_name == "strict":
            return "Strict XLSX read"
        if request.format_name == "xlsx" and request.strategy_name == "detect_tables":
            return "XLSX table detection"
        return f"{request.format_name}.{request.strategy_name}"
