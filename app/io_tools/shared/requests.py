"""
Публичные DTO запросов импорта и экспорта.

Запросы вынесены в общий пакет, чтобы верхние фасады, dispatcher-ы и
реестры flow-ов работали с единым контрактом. Старые модули из слоя
`application` могут переэкспортировать эти классы без собственной логики.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.io_tools.shared.tabular.payloads import ExportPayload


ImportFormat = Literal["xlsx"] | str
ImportStrategy = Literal[
    "standard",
    "range",
    "smart",
    "smart_detailed",
    "strict",
    "detect_tables",
] | str
ImportDestination = Literal["return"] | str

ExportFormat = Literal["xlsx"] | str
ExportStrategy = Literal["standard"] | str
ExportDestination = Literal["file"] | str


@dataclass(slots=True)
class ImportRequest:
    """
    Описывает публичный запрос на импорт данных.
    """

    source_path: Path
    format_name: ImportFormat = "xlsx"
    strategy_name: ImportStrategy = "standard"
    destination_name: ImportDestination = "return"
    sheet_name: str | None = None
    cell_range: str | None = None
    entity_type: str | None = None
    min_score: float | None = 0.45
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExportRequest:
    """
    Описывает публичный запрос на экспорт данных.
    """

    payload: ExportPayload
    target_path: Path
    format_name: ExportFormat = "xlsx"
    strategy_name: ExportStrategy = "standard"
    destination_name: ExportDestination = "file"
    options: dict[str, Any] = field(default_factory=dict)
