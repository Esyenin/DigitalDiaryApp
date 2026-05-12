"""
Обработка распознанных XLSX-таблиц с сохранением карты соответствий.

Модуль строит промежуточное представление, удобное для UI и ручной проверки:

- показывает, как каждый заголовок таблицы был интерпретирован;
- сохраняет исходные строки рядом с нормализованными и разрешенными данными;
- собирает готовые `create_payloads`, не теряя трассировку распознавания.

Этот слой не работает с базой данных напрямую. Он переиспользует существующие
нормализацию, резолв ссылок и финальную подготовку payload-ов.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging

from app.io_tools.xlsx_importer.data_normalizer import (
    DataNormalizer,
    DataResolver,
    ImportProcessingResult,
    ImportProcessor,
    NormalizedRow,
    ResolvedRow,
)
from app.io_tools.xlsx_importer.raw_reader import ExtractedTable


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HeaderBinding:
    """
    Описывает, как один исходный заголовок был распознан системой.
    """

    source_header: str
    normalized_header: str
    binding_type: str
    target_path: str | None = None


@dataclass(slots=True)
class ProcessedRow:
    """
    Хранит полную картину обработки одной строки таблицы.
    """

    source_row_number: int
    source_values: dict[str, object]
    normalized_data: dict[str, object] = field(default_factory=dict)
    references: dict[str, dict[str, object]] = field(default_factory=dict)
    resolved_data: dict[str, object] = field(default_factory=dict)
    resolved_references: dict[str, dict[str, object]] = field(default_factory=dict)
    unresolved_references: dict[str, dict[str, object]] = field(default_factory=dict)
    unmapped: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    create_payload: dict[str, object] | None = None

    @property
    def is_valid(self) -> bool:
        """
        Показывает, можно ли использовать строку для импорта без дополнительной правки.

        :return: `True`, если в строке нет ошибок.
        """
        return not self.errors


@dataclass(slots=True)
class DataProcessingResult:
    """
    Хранит полную картину обработки одной распознанной таблицы.
    """

    entity_type: str
    source_sheet: str
    source_range: str
    header_bindings: list[HeaderBinding] = field(default_factory=list)
    rows: list[ProcessedRow] = field(default_factory=list)
    create_payloads: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, готова ли таблица к безопасному применению результатов обработки.

        :return: `True`, если в таблице нет ошибок верхнего уровня.
        """
        return not self.errors


class DataProcessor:
    """
    Строит полное представление обработки smart-таблицы для UI и следующего слоя импорта.

    Порядок работы:

    1. Сохраняет карту соответствий заголовков.
    2. Запускает нормализацию и разрешение ссылок.
    3. Строит итоговые `create_payloads`.
    4. Склеивает все результаты в единый объект `DataProcessingResult`.
    """

    def __init__(
        self,
        *,
        data_normalizer: DataNormalizer | None = None,
        data_resolver: DataResolver | None = None,
        import_processor: ImportProcessor | None = None,
    ) -> None:
        """
        Создает слой обработки данных smart-импорта.

        :param data_normalizer: Пользовательский нормализатор данных.
        :param data_resolver: Пользовательский резолвер ссылок.
        :param import_processor: Пользовательский процессор итоговой подготовки
            payload-ов.
        """
        self.data_normalizer = data_normalizer or DataNormalizer()
        self.data_resolver = data_resolver or DataResolver()
        self.import_processor = import_processor or ImportProcessor(
            data_normalizer=self.data_normalizer,
            data_resolver=self.data_resolver,
        )

    def process_table(self, extracted_table: ExtractedTable) -> DataProcessingResult:
        """
        Обрабатывает распознанную таблицу и сохраняет трассировку распознавания.

        :param extracted_table: Таблица, прочитанная из произвольного диапазона.
        :return: Полный результат обработки с картой заголовков, построчными
            результатами и итоговыми payload-ами.
        """
        logger.info(
            "DataProcessor started. entity_type=%s sheet=%s range=%s.",
            extracted_table.entity_type,
            extracted_table.sheet,
            extracted_table.range,
        )
        if extracted_table.entity_type is None:
            raise ValueError("Extracted table must contain entity_type.")

        header_bindings = self._build_header_bindings(
            extracted_table.entity_type,
            extracted_table.headers,
        )
        import_result = self.import_processor.process_table(extracted_table)
        processed_rows = self._build_processed_rows(extracted_table, import_result)

        result = DataProcessingResult(
            entity_type=extracted_table.entity_type,
            source_sheet=extracted_table.sheet,
            source_range=extracted_table.range,
            header_bindings=header_bindings,
            rows=processed_rows,
            create_payloads=list(import_result.create_payloads),
            warnings=list(extracted_table.warnings) + list(import_result.warnings),
            errors=list(extracted_table.errors) + list(import_result.errors),
        )
        logger.info(
            "DataProcessor finished. entity_type=%s rows=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.rows),
            len(result.create_payloads),
            len(result.errors),
        )
        return result

    def _build_header_bindings(
        self,
        entity_type: str,
        headers: tuple[str, ...],
    ) -> list[HeaderBinding]:
        """
        Строит карту соответствий заголовков исходной таблицы.

        :param entity_type: Канонический тип сущности.
        :param headers: Заголовки таблицы в исходном порядке.
        :return: Список распознанных привязок заголовков.
        """
        bindings: list[HeaderBinding] = []
        for header in headers:
            binding_type, target_path = self.data_normalizer.describe_header_binding(
                entity_type,
                header,
            )
            bindings.append(
                HeaderBinding(
                    source_header=header,
                    normalized_header=self.data_normalizer.normalize_header(header),
                    binding_type=binding_type,
                    target_path=target_path,
                )
            )
        return bindings

    @staticmethod
    def _build_processed_rows(
        extracted_table: ExtractedTable,
        import_result: ImportProcessingResult,
    ) -> list[ProcessedRow]:
        """
        Склеивает исходные строки с результатами нормализации и подготовки payload-ов.

        :param extracted_table: Исходная таблица диапазона.
        :param import_result: Результат нормализации, резолва и подготовки.
        :return: Построчная детализация обработки.
        """
        payload_by_row_number = {
            row.normalized_row.source_row_number: payload
            for row, payload in zip(
                (
                    resolved_row
                    for resolved_row in import_result.resolved_rows
                    if resolved_row.is_valid
                ),
                import_result.create_payloads,
            )
        }

        normalized_by_row_number = {
            row.source_row_number: row
            for row in import_result.normalized_rows
        }
        resolved_by_row_number = {
            row.normalized_row.source_row_number: row
            for row in import_result.resolved_rows
        }

        processed_rows: list[ProcessedRow] = []
        for row_index, source_values in enumerate(extracted_table.rows, start=2):
            normalized_row = normalized_by_row_number.get(row_index)
            resolved_row = resolved_by_row_number.get(row_index)

            processed_rows.append(
                ProcessedRow(
                    source_row_number=row_index,
                    source_values=dict(source_values),
                    normalized_data=dict(normalized_row.data) if normalized_row else {},
                    references=dict(normalized_row.references) if normalized_row else {},
                    resolved_data=dict(resolved_row.data) if resolved_row else {},
                    resolved_references=(
                        dict(resolved_row.resolved_references)
                        if resolved_row
                        else {}
                    ),
                    unresolved_references=(
                        dict(resolved_row.unresolved_references)
                        if resolved_row
                        else {}
                    ),
                    unmapped=dict(normalized_row.unmapped) if normalized_row else {},
                    warnings=(
                        list(normalized_row.warnings) + list(resolved_row.warnings)
                        if normalized_row and resolved_row
                        else list(normalized_row.warnings)
                        if normalized_row
                        else list(resolved_row.warnings)
                        if resolved_row
                        else []
                    ),
                    errors=(
                        list(normalized_row.errors) + list(resolved_row.errors)
                        if normalized_row and resolved_row
                        else list(normalized_row.errors)
                        if normalized_row
                        else list(resolved_row.errors)
                        if resolved_row
                        else []
                    ),
                    create_payload=payload_by_row_number.get(row_index),
                )
            )

        return processed_rows
