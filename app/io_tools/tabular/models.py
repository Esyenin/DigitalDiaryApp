"""
Общие модели табличных данных, которые используются между слоями `io_tools`.

Модуль специально не привязан к конкретному формату файла. Он описывает:

1. Геометрию найденной табличной области.
2. Результат чтения и первичной валидации диапазона.

Такие модели могут использоваться не только для XLSX. Если в проекте появятся
CSV, TSV или иной табличный источник, верхние слои смогут переиспользовать эти
же структуры без копирования контрактов и без привязки к Excel-реализации.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TableRegion:
    """
    Описывает найденную прямоугольную область, похожую на таблицу.

    Модель хранит координаты области, её размеры и статистику, по которой
    низкоуровневый reader признал диапазон похожим на таблицу.
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
class ExtractedTable:
    """
    Хранит данные уже прочитанной табличной области.

    Помимо строк модуль сохраняет структурную диагностику: какие заголовки
    были распознаны, каких обязательных колонок не хватило, а также warnings
    и errors, полученные ещё до прикладной обработки smart/strict-слоем.
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

    @property
    def is_valid(self) -> bool:
        """
        Показывает, прошла ли таблица базовую структурную проверку.

        :return: `True`, если критических ошибок не найдено.
        """
        return not self.errors
