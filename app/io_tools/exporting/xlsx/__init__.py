"""
XLSX-компоненты export-слоя.

Пакет оставлен лёгким: фасад экспорта подгружается лениво, чтобы избежать
циклов между dispatcher, writer и compatibility-импортами.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["XlsxExportFacade"]


def __getattr__(name: str) -> Any:
    """
    Лениво возвращает экспортный фасад XLSX.
    """
    if name == "XlsxExportFacade":
        return import_module("app.io_tools.exporting.xlsx.exporter").XlsxExportFacade
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
