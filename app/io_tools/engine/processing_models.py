"""
Модели результатов и промежуточных данных для smart/strict импорта.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NormalizedRow:
    """
    Хранит строку после распознавания прямых и ссылочных полей.
    """

    source_sheet: str
    source_range: str
    source_row_number: int
    entity_type: str
    data: dict[str, object] = field(default_factory=dict)
    references: dict[str, dict[str, object]] = field(default_factory=dict)
    unmapped: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, что в строке нет критических ошибок нормализации.

        :return: `True`, если ошибок нет.
        """
        return not self.errors


@dataclass(slots=True)
class ResolvedRow:
    """
    Хранит строку после попытки разрешения ссылок.
    """

    normalized_row: NormalizedRow
    data: dict[str, object]
    resolved_references: dict[str, dict[str, object]] = field(default_factory=dict)
    unresolved_references: dict[str, dict[str, object]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, что строку можно использовать дальше без исправлений.

        :return: `True`, если ошибок нет.
        """
        return not self.errors


@dataclass(slots=True)
class ImportProcessingResult:
    """
    Хранит итог smart-подготовки таблицы к импорту.
    """

    entity_type: str
    normalized_rows: list[NormalizedRow] = field(default_factory=list)
    resolved_rows: list[ResolvedRow] = field(default_factory=list)
    create_payloads: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, что итог подготовки не содержит ошибок.

        :return: `True`, если ошибок нет.
        """
        return not self.errors


@dataclass(slots=True)
class HeaderBinding:
    """
    Описывает, как был распознан один заголовок таблицы.
    """

    source_header: str
    normalized_header: str
    binding_type: str
    target_path: str | None = None


@dataclass(slots=True)
class ProcessedRow:
    """
    Хранит подробную трассировку обработки одной строки.
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
        Показывает, что строка не содержит ошибок.

        :return: `True`, если ошибок нет.
        """
        return not self.errors


@dataclass(slots=True)
class DataProcessingResult:
    """
    Хранит полную картину smart-обработки таблицы.
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
        Показывает, что таблица не содержит ошибок верхнего уровня.

        :return: `True`, если ошибок нет.
        """
        return not self.errors


@dataclass(slots=True)
class StrictImportResult:
    """
    Хранит итог строгой подготовки таблицы к импорту.
    """

    entity_type: str
    rows: list[dict[str, object]] = field(default_factory=list)
    create_payloads: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, что strict-подготовка завершилась без ошибок.

        :return: `True`, если ошибок нет.
        """
        return not self.errors
