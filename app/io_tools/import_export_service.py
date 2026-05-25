"""
Публичный API подсистемы `io_tools`.

Сервис намеренно оставлен очень тонким. Его задача — не выбирать сценарии
вручную и не содержать внутри бизнес-логику импорта, а предоставлять
внешнему коду две стабильные точки входа:

1. `import_data(...)` для чтения табличных данных.
2. `export_data(...)` для выгрузки табличных данных.

Вся маршрутизация по форматам и стратегиям вынесена в dispatcher-слой.
Короткие методы `import_from_xlsx(...)` и `export_to_xlsx(...)` сохранены лишь
как адаптеры для уже существующего кода приложения.
"""
from __future__ import annotations

from pathlib import Path

from app.io_tools.application import (
    ExportDispatcher,
    ExportRequest,
    ImportDispatcher,
    ImportRequest,
)
from app.io_tools.engine.operation_result import TabularImportResult
from app.io_tools.xlsx_exporter import ExportPayload, XlsxExporter
from app.io_tools.xlsx_importer.xlsx_importer import XlsxImporter


class ImportExportService:
    """
    Предоставляет минимальный публичный API импорта и экспорта.

    Сервис больше не хранит внутри маршрутизацию по стратегиям и форматам.
    Он лишь принимает запрос API и делегирует его соответствующему dispatcher.
    """

    def __init__(
        self,
        *,
        xlsx_exporter: XlsxExporter | None = None,
        xlsx_importer: XlsxImporter | None = None,
    ) -> None:
        """
        Создаёт публичный сервис импорта и экспорта.

        :param xlsx_exporter: Пользовательский XLSX-экспортёр.
        :param xlsx_importer: Пользовательский XLSX-импортёр.
        """
        importer = xlsx_importer or XlsxImporter()
        exporter = xlsx_exporter or XlsxExporter()
        self.import_dispatcher = ImportDispatcher(xlsx_importer=importer)
        self.export_dispatcher = ExportDispatcher(xlsx_exporter=exporter)

    def import_data(self, request: ImportRequest) -> object:
        """
        Выполняет импорт по описанию запроса API.

        :param request: Параметры импорта.
        :return: Результат выбранной стратегии.
        """
        return self.import_dispatcher.execute(request)

    def export_data(self, request: ExportRequest) -> Path:
        """
        Выполняет экспорт по описанию запроса API.

        :param request: Параметры экспорта.
        :return: Путь к созданному файлу.
        """
        return self.export_dispatcher.execute(request)

    def import_from_xlsx(
        self,
        file_path: str | Path,
    ) -> dict[str, list[dict[str, object]]]:
        """
        Краткий API стандартного XLSX-импорта для существующего кода приложения.

        :param file_path: Путь к XLSX-файлу.
        :return: Данные по листам.
        :raises ValueError: Если импорт завершился с ошибками.
        """
        result = self.import_data(
            ImportRequest(
                source_path=Path(file_path),
                format_name="xlsx",
                strategy_name="standard",
                destination_name="return",
            )
        )
        assert isinstance(result, TabularImportResult)
        if not result.is_valid:
            first_error = next(
                message.text
                for message in result.messages
                if message.level == "error"
            )
            raise ValueError(first_error)
        return result.data

    def export_to_xlsx(
        self,
        payload: ExportPayload,
        file_path: str | Path,
    ) -> Path:
        """
        Краткий API стандартного XLSX-экспорта для существующего кода приложения.

        :param payload: Подготовленные данные экспорта.
        :param file_path: Целевой путь.
        :return: Путь к созданному XLSX-файлу.
        """
        return self.export_data(
            ExportRequest(
                payload=payload,
                target_path=Path(file_path),
                format_name="xlsx",
                strategy_name="standard",
                destination_name="file",
            )
        )
