"""
Контексты и состояние операций импорта и экспорта.

Модуль задаёт основной контракт обмена данными между слоями `application`,
`engine` и форматными адаптерами. Здесь специально собраны:

1. Контекст импорта.
2. Контекст экспорта.
3. Типизированное промежуточное состояние pipeline.

За счёт этого шаги обработки больше не передают по цепочке неструктурированные
словари и не зависят от случайных ключей вроде `payload["something"]`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.io_tools.engine.processing_models import (
    HeaderBinding,
    ImportProcessingResult,
    NormalizedRow,
    ProcessedRow,
    ResolvedRow,
    StrictImportResult,
)
from app.io_tools.tabular.models import ExtractedTable
from app.io_tools.tabular.payloads import ExportPayload


@dataclass(slots=True)
class ImportOperationState:
    """
    Хранит типизированное промежуточное состояние pipeline импорта.
    """

    extracted_table: ExtractedTable | None = None
    normalized_rows: list[NormalizedRow] = field(default_factory=list)
    resolved_rows: list[ResolvedRow] = field(default_factory=list)
    header_bindings: list[HeaderBinding] = field(default_factory=list)
    processed_rows: list[ProcessedRow] = field(default_factory=list)
    import_result: ImportProcessingResult | None = None
    strict_result: StrictImportResult | None = None
    strict_header_errors: list[str] = field(default_factory=list)
    strict_header_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ImportOperationContext:
    """
    Хранит состояние одной операции чтения и подготовки табличных данных.

    Контекст намеренно сделан универсальным: он не зависит от конкретного
    формата файла и может использоваться не только для XLSX.
    """

    file_path: Path
    sheet_name: str | None = None
    cell_range: str | None = None
    entity_type: str | None = None
    state: ImportOperationState = field(default_factory=ImportOperationState)
    result: Any | None = None

    @classmethod
    def from_extracted_table(cls, extracted_table: ExtractedTable) -> ImportOperationContext:
        """
        Создаёт контекст для уже извлечённой табличной области.

        Такой конструктор нужен, когда таблица уже прочитана из файла и
        дальнейшие шаги должны работать только с её содержимым.

        :param extracted_table: Уже извлечённая таблица с метаданными.
        :return: Контекст операции импорта с заполненным состоянием.
        """
        context = cls(
            file_path=Path("."),
            sheet_name=extracted_table.sheet,
            cell_range=extracted_table.range,
            entity_type=extracted_table.entity_type,
        )
        context.state.extracted_table = extracted_table
        return context


@dataclass(slots=True)
class ExportOperationContext:
    """
    Хранит состояние одной операции экспорта табличных данных.

    В отличие от старого подхода контекст экспорта больше не использует
    неструктурированный словарь payload. Он содержит явное поле
    `export_payload`, понятное верхним слоям и форматным стратегиям.
    """

    file_path: Path
    export_payload: ExportPayload | None = None
    result: Any | None = None
