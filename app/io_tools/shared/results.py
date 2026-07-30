"""
Единые результаты импорта и экспорта.

Новые flow-сценарии должны возвращать стабильные результат-объекты,
которые одинаково удобны и для API, и для логирования, и для будущих
UI-экранов предпросмотра. При этом старые result-классы пока остаются
в проекте ради совместимости и могут жить в `meta["legacy_result"]`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.io_tools.shared.diagnostics import Diagnostic
from app.io_tools.shared.tabular.models import HeaderBinding, NormalizedRow, ProcessedRow, ResolvedRow


@dataclass(slots=True)
class SmartImportDetails:
    """
    Дополнительные детали smart-импорта.
    """

    header_bindings: list[Any] = field(default_factory=list)
    rows: list[Any] = field(default_factory=list)


@dataclass(slots=True)
class StrictImportDetails:
    """
    Дополнительные детали strict-импорта.
    """

    expected_headers: list[str] = field(default_factory=list)
    actual_headers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StandardWorkbookDetails:
    """
    Дополнительные детали стандартного импорта книги.
    """

    sheets: list[str] = field(default_factory=list)
    rows_by_sheet: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class OperationMessage:
    """
    Совместимое текстовое сообщение стандартного табличного импорта.
    """

    level: str
    text: str
    sheet_name: str | None = None
    cell_range: str | None = None
    row_number: int | None = None
    column_name: str | None = None

    def render(self) -> str:
        parts: list[str] = [self.text]
        if self.sheet_name is not None:
            parts.append(f"sheet={self.sheet_name}")
        if self.cell_range is not None:
            parts.append(f"range={self.cell_range}")
        if self.row_number is not None:
            parts.append(f"row={self.row_number}")
        if self.column_name is not None:
            parts.append(f"column={self.column_name}")
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} ({', '.join(parts[1:])})"


@dataclass(slots=True)
class TabularImportResult:
    """
    Совместимый результат стандартного чтения табличного файла.
    """

    data: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    messages: list[OperationMessage] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        return [
            message.render()
            for message in self.messages
            if message.level == "warning"
        ]

    @property
    def errors(self) -> list[str]:
        return [
            message.render()
            for message in self.messages
            if message.level == "error"
        ]

    @property
    def is_valid(self) -> bool:
        return not any(message.level == "error" for message in self.messages)

    def add_warning(
        self,
        text: str,
        *,
        sheet_name: str | None = None,
        cell_range: str | None = None,
        row_number: int | None = None,
        column_name: str | None = None,
    ) -> None:
        self.messages.append(
            OperationMessage(
                level="warning",
                text=text,
                sheet_name=sheet_name,
                cell_range=cell_range,
                row_number=row_number,
                column_name=column_name,
            )
        )

    def add_error(
        self,
        text: str,
        *,
        sheet_name: str | None = None,
        cell_range: str | None = None,
        row_number: int | None = None,
        column_name: str | None = None,
    ) -> None:
        self.messages.append(
            OperationMessage(
                level="error",
                text=text,
                sheet_name=sheet_name,
                cell_range=cell_range,
                row_number=row_number,
                column_name=column_name,
            )
        )


@dataclass(slots=True)
class ImportProcessingResult:
    """
    Совместимый итог smart-подготовки таблицы к импорту.
    """

    entity_type: str
    normalized_rows: list[NormalizedRow] = field(default_factory=list)
    resolved_rows: list[ResolvedRow] = field(default_factory=list)
    create_payloads: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class DataProcessingResult:
    """
    Совместимая полная картина smart-обработки таблицы.
    """

    entity_type: str
    source_sheet: str
    source_range: str
    header_bindings: list[HeaderBinding] = field(default_factory=list)
    rows: list[ProcessedRow] = field(default_factory=list)
    create_payloads: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class StrictImportResult:
    """
    Совместимый итог строгой подготовки таблицы к импорту.
    """

    entity_type: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    create_payloads: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class ImportResult:
    """
    Унифицированный результат сценария импорта.

    Модель не навязывает конкретный режим импорта. В неё помещаются и
    готовые payload-ы, и диагностические сообщения, и опциональные детали
    сценария. Для обратной совместимости legacy-результат можно хранить
    в `meta["legacy_result"]`.
    """

    entity_type: str | None
    payloads: list[dict[str, Any]]
    diagnostics: list[Diagnostic]
    rows: list[Any] = field(default_factory=list)
    details: Any | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, завершился ли сценарий без ошибок.
        """
        return not any(
            diagnostic.level in {"error", "critical"}
            for diagnostic in self.diagnostics
        )

    @property
    def warnings(self) -> list[str]:
        """
        Возвращает предупреждения в текстовом виде для совместимости.
        """
        return [
            diagnostic.render()
            for diagnostic in self.diagnostics
            if diagnostic.level == "warning"
        ]

    @property
    def errors(self) -> list[str]:
        """
        Возвращает ошибки в текстовом виде для совместимости.
        """
        return [
            diagnostic.render()
            for diagnostic in self.diagnostics
            if diagnostic.level in {"error", "critical"}
        ]

    @property
    def create_payloads(self) -> list[dict[str, Any]]:
        """
        Совместимый алиас для старого имени поля.
        """
        return self.payloads

    @property
    def legacy_result(self) -> Any | None:
        """
        Возвращает legacy-результат, если flow сохранил его в `meta`.
        """
        return self.meta.get("legacy_result")


@dataclass(slots=True)
class ExportResult:
    """
    Унифицированный результат сценария экспорта.
    """

    target_path: Path | None
    diagnostics: list[Diagnostic]
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, завершился ли экспорт без ошибок.
        """
        return not any(
            diagnostic.level in {"error", "critical"}
            for diagnostic in self.diagnostics
        )

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
