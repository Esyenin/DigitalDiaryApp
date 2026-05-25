"""
Единый формат предупреждений и ошибок операций импорта и экспорта.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MessageLevel = Literal["warning", "error"]


@dataclass(slots=True)
class OperationMessage:
    """
    Описывает одно диагностическое сообщение операции.

    Сообщение может быть как предупреждением, так и ошибкой. При наличии
    координат источник сообщения можно показать в UI или в логах точнее,
    чем простую строку.
    """

    level: MessageLevel
    text: str
    sheet_name: str | None = None
    cell_range: str | None = None
    row_number: int | None = None
    column_name: str | None = None

    def render(self) -> str:
        """
        Возвращает человекочитаемый текст сообщения с координатами.

        :return: Строка для логирования или отображения в интерфейсе.
        """
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
