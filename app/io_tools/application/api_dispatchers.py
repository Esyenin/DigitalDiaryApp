"""
Маршрутизация публичных API-запросов импорта и экспорта.

Задача этого модуля — не выполнять сам импорт и не читать файлы напрямую, а
связывать внешний API с внутренними обработчиками. По сути это слой
диспетчеризации, который:

1. Валидирует комбинацию `format + strategy + destination`.
2. Выбирает зарегистрированный обработчик маршрута.
3. Применяет единое логирование диагностики результата.

Такой подход позволяет держать `ImportExportService` тонким и не размазывать
по нему логику выбора сценариев.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path

from app.io_tools.application.api_requests import ExportRequest, ImportRequest
from app.io_tools.engine.operation_context import ExportOperationContext
from app.io_tools.formats.xlsx.strategies import StandardExportStrategy
from app.io_tools.xlsx_exporter import XlsxExporter
from app.io_tools.xlsx_importer.xlsx_importer import XlsxImporter


logger = logging.getLogger(__name__)

ImportHandler = Callable[[ImportRequest], object]
ExportHandler = Callable[[ExportRequest], Path]


@dataclass(frozen=True, slots=True)
class RouteKey:
    """
    Представляет ключ маршрута API.

    Через такой ключ dispatcher связывает внешний запрос с конкретным
    обработчиком, не полагаясь на цепочки условных операторов.
    """

    format_name: str
    strategy_name: str
    destination_name: str


class DiagnosticsLogger:
    """
    Логирует warnings и errors результата в едином стиле.
    """

    @staticmethod
    def log(operation_name: str, result: object) -> None:
        """
        Пишет предупреждения и ошибки результата в лог.

        :param operation_name: Имя операции.
        :param result: Результат с полями `warnings` и `errors`.
        :return: `None`.
        """
        warnings = list(getattr(result, "warnings", []))
        errors = list(getattr(result, "errors", []))

        if warnings:
            logger.debug("%s warnings: %s.", operation_name, warnings)
        if errors:
            logger.warning(
                "%s returned validation errors: %s.",
                operation_name,
                errors,
            )


class ImportDispatcher:
    """
    Выбирает обработчик импорта по формату, стратегии и destination.
    """

    def __init__(
        self,
        *,
        xlsx_importer: XlsxImporter | None = None,
        routes: dict[RouteKey, ImportHandler] | None = None,
    ) -> None:
        """
        Создаёт dispatcher публичного API импорта.

        :param xlsx_importer: XLSX-импортёр, используемый маршрутами по умолчанию.
        :param routes: Пользовательский реестр маршрутов.
        """
        self.xlsx_importer = xlsx_importer or XlsxImporter()
        self.routes = routes or self._build_default_routes()

    def execute(self, request: ImportRequest) -> object:
        """
        Выполняет импорт в соответствии с API-запросом.

        :param request: Параметры импорта.
        :return: Результат зарегистрированного обработчика.
        :raises ValueError: Если маршрут не зарегистрирован.
        """
        route_key = RouteKey(
            request.format_name,
            request.strategy_name,
            request.destination_name,
        )
        handler = self.routes.get(route_key)
        if handler is None:
            raise ValueError(
                "Unsupported import route: "
                f"format={request.format_name!r}, "
                f"strategy={request.strategy_name!r}, "
                f"destination={request.destination_name!r}."
            )

        logger.info(
            "Import requested. format=%s strategy=%s source=%s destination=%s.",
            request.format_name,
            request.strategy_name,
            request.source_path,
            request.destination_name,
        )
        return handler(request)

    def _build_default_routes(self) -> dict[RouteKey, ImportHandler]:
        """
        Создаёт стандартный реестр маршрутов импорта.

        :return: Словарь `RouteKey -> handler`.
        """
        return {
            RouteKey("xlsx", "standard", "return"): self._handle_standard_xlsx,
            RouteKey("xlsx", "detect_tables", "return"): self._handle_detect_tables,
            RouteKey("xlsx", "range", "return"): self._handle_range_xlsx,
            RouteKey("xlsx", "smart", "return"): self._handle_smart_xlsx,
            RouteKey(
                "xlsx",
                "smart_detailed",
                "return",
            ): self._handle_smart_detailed_xlsx,
            RouteKey("xlsx", "strict", "return"): self._handle_strict_xlsx,
        }

    def _handle_standard_xlsx(self, request: ImportRequest) -> object:
        result = self.xlsx_importer.read_standard_workbook(request.source_path)
        DiagnosticsLogger.log("Standard XLSX read", result)
        return result

    def _handle_detect_tables(self, request: ImportRequest) -> object:
        return self.xlsx_importer.find_table_candidates(
            request.source_path,
            min_score=request.min_score,
        )

    def _handle_range_xlsx(self, request: ImportRequest) -> object:
        result = self.xlsx_importer.read_table_range(
            request.source_path,
            request.sheet_name or "",
            request.cell_range or "",
            entity_type=request.entity_type,
        )
        DiagnosticsLogger.log("XLSX range read", result)
        return result

    def _handle_smart_xlsx(self, request: ImportRequest) -> object:
        result = self.xlsx_importer.read_smart_table(
            request.source_path,
            request.sheet_name or "",
            request.cell_range or "",
            entity_type=request.entity_type or "",
        )
        DiagnosticsLogger.log("Smart XLSX read", result)
        return result

    def _handle_smart_detailed_xlsx(self, request: ImportRequest) -> object:
        result = self.xlsx_importer.process_smart_table(
            request.source_path,
            request.sheet_name or "",
            request.cell_range or "",
            entity_type=request.entity_type or "",
        )
        DiagnosticsLogger.log("Smart XLSX processing", result)
        return result

    def _handle_strict_xlsx(self, request: ImportRequest) -> object:
        result = self.xlsx_importer.read_strict_table(
            request.source_path,
            request.sheet_name or "",
            request.cell_range or "",
            entity_type=request.entity_type or "",
        )
        DiagnosticsLogger.log("Strict XLSX read", result)
        return result


class ExportDispatcher:
    """
    Выбирает обработчик экспорта по формату, стратегии и destination.
    """

    def __init__(
        self,
        *,
        xlsx_exporter: XlsxExporter | None = None,
        standard_export_strategy: StandardExportStrategy | None = None,
        routes: dict[RouteKey, ExportHandler] | None = None,
    ) -> None:
        """
        Создаёт dispatcher публичного API экспорта.

        :param xlsx_exporter: XLSX-экспортёр для маршрутов по умолчанию.
        :param standard_export_strategy: Пользовательская стратегия экспорта.
        :param routes: Пользовательский реестр маршрутов.
        """
        self.standard_export_strategy = (
            standard_export_strategy
            or StandardExportStrategy(
                xlsx_exporter=xlsx_exporter,
            )
        )
        self.routes = routes or self._build_default_routes()

    def execute(self, request: ExportRequest) -> Path:
        """
        Выполняет экспорт в соответствии с API-запросом.

        :param request: Параметры экспорта.
        :return: Путь к созданному файлу.
        :raises ValueError: Если маршрут не зарегистрирован.
        """
        route_key = RouteKey(
            request.format_name,
            request.strategy_name,
            request.destination_name,
        )
        handler = self.routes.get(route_key)
        if handler is None:
            raise ValueError(
                "Unsupported export route: "
                f"format={request.format_name!r}, "
                f"strategy={request.strategy_name!r}, "
                f"destination={request.destination_name!r}."
            )

        logger.info(
            "Export requested. format=%s strategy=%s target=%s destination=%s.",
            request.format_name,
            request.strategy_name,
            request.target_path,
            request.destination_name,
        )
        return handler(request)

    def _build_default_routes(self) -> dict[RouteKey, ExportHandler]:
        """
        Создаёт стандартный реестр маршрутов экспорта.

        :return: Словарь `RouteKey -> handler`.
        """
        return {
            RouteKey("xlsx", "standard", "file"): self._handle_standard_xlsx,
        }

    def _handle_standard_xlsx(self, request: ExportRequest) -> Path:
        context = ExportOperationContext(
            file_path=request.target_path,
            export_payload=request.payload,
        )
        exported_path = self.standard_export_strategy.execute(context)
        logger.info("Export finished. target=%s.", exported_path)
        return exported_path
