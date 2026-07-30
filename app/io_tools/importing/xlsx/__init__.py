"""
XLSX-сценарии нового import-слоя.

Пакет объединяет фасад `XlsxImporter`, отдельные режимы импорта и общие
flow-сценарии чтения диапазонов и поиска таблиц. Основная логика здесь
организована по сценариям, а не по искусственным слоям.
"""

from app.io_tools.importing.xlsx.importer import XlsxImporter

__all__ = ["XlsxImporter"]
