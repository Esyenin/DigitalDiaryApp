"""
Контракты публичного API слоя `io_tools`.

Модуль задаёт стабильные объекты запросов, через которые внешний код должен
общаться с подсистемой импорта и экспорта. Такой подход нужен, чтобы:

1. Не плодить десятки специализированных методов верхнего сервиса.
2. Явно описывать формат, стратегию и destination операции.
3. Сохранять читаемость API при расширении списка сценариев.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.io_tools.tabular.payloads import ExportPayload


ImportFormat = Literal["xlsx"]
ImportStrategy = Literal[
    "standard",
    "range",
    "smart",
    "smart_detailed",
    "strict",
    "detect_tables",
]
ImportDestination = Literal["return"]
ExportFormat = Literal["xlsx"]
ExportStrategy = Literal["standard"]
ExportDestination = Literal["file"]


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
    min_score: float = 0.45


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
