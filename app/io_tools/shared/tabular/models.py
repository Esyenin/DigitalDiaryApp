"""
Общие модели табличных данных.

Модели в этом файле используются между reader-ами, processor-ами,
builder-ами и flow-сценариями. Они стараются быть максимально
формат-независимыми, но при этом сохраняют совместимость с текущими
XLSX-сценариями и тестами проекта.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.io_tools.shared.diagnostics import Diagnostic, DiagnosticCollector


@dataclass(slots=True)
class TableRegion:
    """
    Описывает найденную прямоугольную область, похожую на таблицу.
    """

    sheet: str
    range: str
    min_row: int
    max_row: int
    min_col: int
    max_col: int
    rows: int
    cols: int
    total_cells: int
    non_empty_cells: int
    density: float
    score: float


@dataclass(slots=True)
class HeaderBinding:
    """
    Описывает сопоставление одного заголовка с целевым полем.
    """

    source_header: str
    normalized_header: str
    binding_type: str
    target_path: str | None = None
    confidence: float | None = None


@dataclass(slots=True)
class RowProcessingState:
    """
    Хранит полное состояние обработки одной строки.

    Эта модель заменяет связку из нескольких legacy-структур и позволяет
    и smart-, и strict-сценариям опираться на один и тот же формат трассы
    обработки.
    """

    row_number: int
    source_values: dict[str, Any]
    normalized_values: dict[str, Any] = field(default_factory=dict)
    references: dict[str, dict[str, Any]] = field(default_factory=dict)
    resolved_values: dict[str, Any] = field(default_factory=dict)
    unmapped_values: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        return [
            diagnostic.render()
            for diagnostic in self.diagnostics
            if diagnostic.level == "warning"
        ]

    @property
    def errors(self) -> list[str]:
        return [
            diagnostic.render()
            for diagnostic in self.diagnostics
            if diagnostic.level in {"error", "critical"}
        ]

    @property
    def is_valid(self) -> bool:
        return not any(
            diagnostic.level in {"error", "critical"}
            for diagnostic in self.diagnostics
        )


@dataclass(slots=True)
class NormalizedRow:
    """
    Совместимая модель строки после распознавания прямых и ссылочных полей.
    """

    source_sheet: str
    source_range: str
    source_row_number: int
    entity_type: str
    data: dict[str, Any] = field(default_factory=dict)
    references: dict[str, dict[str, Any]] = field(default_factory=dict)
    unmapped: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class ResolvedRow:
    """
    Совместимая модель строки после попытки разрешения ссылок.
    """

    normalized_row: NormalizedRow
    data: dict[str, Any]
    resolved_references: dict[str, dict[str, Any]] = field(default_factory=dict)
    unresolved_references: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class ProcessedRow:
    """
    Совместимая подробная трассировка обработки одной строки.
    """

    source_row_number: int
    source_values: dict[str, Any]
    normalized_data: dict[str, Any] = field(default_factory=dict)
    references: dict[str, dict[str, Any]] = field(default_factory=dict)
    resolved_data: dict[str, Any] = field(default_factory=dict)
    resolved_references: dict[str, dict[str, Any]] = field(default_factory=dict)
    unresolved_references: dict[str, dict[str, Any]] = field(default_factory=dict)
    unmapped: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    create_payload: dict[str, Any] | None = None

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class ExtractedTable:
    """
    Хранит уже прочитанную табличную область и её базовую диагностику.

    Модель специально сохраняет legacy-поля `warnings` и `errors`, потому
    что они всё ещё используются существующим кодом и тестами. При этом
    новый код может работать через структурированные `diagnostics`.
    """

    sheet: str
    range: str
    entity_type: str | None
    headers: tuple[str, ...]
    rows: list[dict[str, object]]
    known_headers: tuple[str, ...] = ()
    unknown_headers: tuple[str, ...] = ()
    missing_required_headers: tuple[str, ...] = ()
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def __post_init__(self) -> None:
        """
        Синхронизирует legacy-поля `warnings/errors` с новой диагностикой.
        """
        if self.diagnostics:
            if not self.warnings:
                self.warnings = [
                    diagnostic.render()
                    for diagnostic in self.diagnostics
                    if diagnostic.level == "warning"
                ]
            if not self.errors:
                self.errors = [
                    diagnostic.render()
                    for diagnostic in self.diagnostics
                    if diagnostic.level in {"error", "critical"}
                ]
            return

        collector = DiagnosticCollector()
        for warning in self.warnings:
            collector.warning(
                "legacy.warning",
                warning,
                sheet_name=self.sheet,
                cell_range=self.range,
            )
        for error in self.errors:
            collector.error(
                "legacy.error",
                error,
                sheet_name=self.sheet,
                cell_range=self.range,
            )
        self.diagnostics = collector.diagnostics

    @property
    def is_valid(self) -> bool:
        """
        Показывает, прошла ли таблица базовую структурную проверку.
        """
        return not self.errors

    @property
    def sheet_name(self) -> str:
        """
        Совместимый алиас для UI- и diagnostic-контекстов.
        """
        return self.sheet

    @property
    def cell_range(self) -> str:
        """
        Совместимый алиас имени диапазона.
        """
        return self.range
