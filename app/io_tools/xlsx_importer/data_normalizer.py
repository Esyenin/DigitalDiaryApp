"""
Тонкие обёртки над новым smart-pipeline импорта.
"""
from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError

from app.io_tools.application.import_use_cases import PrepareSmartImportUseCase
from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.processing_models import (
    ImportProcessingResult,
    NormalizedRow,
    ResolvedRow,
)
from app.io_tools.engine.steps.smart_steps import (
    SmartReferenceResolver,
    SmartRowNormalizer,
    validation_errors_to_messages,
)
from app.io_tools.tabular.models import ExtractedTable


ResolverCallback = Callable[[dict[str, object]], dict[str, object] | None]


class DataNormalizer:
    """
    Обёртка над сервисом нормализации строк smart-импорта.
    """

    def __init__(self) -> None:
        """
        Создаёт нормализатор данных.
        """
        self.row_normalizer = SmartRowNormalizer()

    def normalize_table(self, extracted_table: ExtractedTable) -> list[NormalizedRow]:
        """
        Нормализует все строки извлечённой таблицы.

        :param extracted_table: Извлечённая таблица.
        :return: Нормализованные строки.
        """
        return self.row_normalizer.normalize_table(extracted_table)

    def normalize_row(
        self,
        entity_type: str,
        raw_row: dict[str, object],
        *,
        source_sheet: str,
        source_range: str,
        source_row_number: int,
    ) -> NormalizedRow:
        """
        Нормализует одну строку.

        :param entity_type: Тип сущности.
        :param raw_row: Исходная строка.
        :param source_sheet: Имя листа.
        :param source_range: Диапазон.
        :param source_row_number: Номер строки.
        :return: Нормализованная строка.
        """
        return self.row_normalizer.normalize_row(
            entity_type,
            raw_row,
            source_sheet=source_sheet,
            source_range=source_range,
            source_row_number=source_row_number,
        )

    @staticmethod
    def normalize_header(header: str) -> str:
        """
        Нормализует заголовок колонки.

        :param header: Исходный заголовок.
        :return: Нормализованный заголовок.
        """
        return SmartRowNormalizer.normalize_header(header)

    def describe_header_binding(
        self,
        entity_type: str,
        header: str,
    ) -> tuple[str, str | None]:
        """
        Описывает привязку заголовка к полю модели.

        :param entity_type: Тип сущности.
        :param header: Исходный заголовок.
        :return: Тип привязки и путь назначения.
        """
        return self.row_normalizer.describe_header_binding(entity_type, header)

    @staticmethod
    def _validation_errors_to_messages(exc: ValidationError) -> list[str]:
        """
        Преобразует ошибки валидации к короткому текстовому виду.

        :param exc: Исключение валидации.
        :return: Список текстов ошибок.
        """
        return validation_errors_to_messages(exc)


class DataResolver:
    """
    Обёртка над сервисом разрешения ссылок smart-импорта.
    """

    def __init__(
        self,
        *,
        reference_resolvers: dict[str, ResolverCallback] | None = None,
    ) -> None:
        """
        Создаёт резолвер ссылок.

        :param reference_resolvers: Callback-функции разрешения ссылок.
        """
        self.reference_resolver = SmartReferenceResolver(
            reference_resolvers=reference_resolvers,
        )

    def resolve_rows(self, normalized_rows: list[NormalizedRow]) -> list[ResolvedRow]:
        """
        Разрешает ссылки у набора строк.

        :param normalized_rows: Нормализованные строки.
        :return: Разрешённые строки.
        """
        return self.reference_resolver.resolve_rows(normalized_rows)

    def resolve_row(self, normalized_row: NormalizedRow) -> ResolvedRow:
        """
        Разрешает ссылки одной строки.

        :param normalized_row: Нормализованная строка.
        :return: Разрешённая строка.
        """
        return self.reference_resolver.resolve_row(normalized_row)


class ImportProcessor:
    """
    Тонкий координатор smart-подготовки payload-ов.
    """

    def __init__(
        self,
        *,
        data_normalizer: DataNormalizer | None = None,
        data_resolver: DataResolver | None = None,
    ) -> None:
        """
        Создаёт процессор подготовки smart-импорта.

        :param data_normalizer: Пользовательский нормализатор.
        :param data_resolver: Пользовательский резолвер ссылок.
        """
        self.data_normalizer = data_normalizer or DataNormalizer()
        self.data_resolver = data_resolver or DataResolver()
        self.use_case = PrepareSmartImportUseCase(
            row_normalizer=self.data_normalizer.row_normalizer,
            reference_resolver=self.data_resolver.reference_resolver,
        )

    def process_table(self, extracted_table: ExtractedTable) -> ImportProcessingResult:
        """
        Полностью подготавливает таблицу до create-payload-ов.

        :param extracted_table: Извлечённая таблица.
        :return: Результат smart-подготовки.
        """
        context = ImportOperationContext.from_extracted_table(extracted_table)
        return self.use_case.execute(context)
