"""
Единый формат диагностики табличных операций.

Модуль нужен, чтобы предупреждения и ошибки больше не передавались
в виде разрозненных `list[str]`, когда информация о строке, колонке
или диапазоне теряется. Новый формат подходит и для логирования,
и для отображения в UI, и для обратной совместимости со старым API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal


DiagnosticLevel = Literal["info", "warning", "error", "critical"]


@dataclass(slots=True, frozen=True)
class Diagnostic:
    """
    Описывает одно диагностическое сообщение операции.

    Диагностика хранит не только человекочитаемый текст, но и контекст:
    лист, диапазон, строку и колонку. Это позволяет одинаково удобно
    использовать её и в логах, и в пользовательском интерфейсе.
    """

    level: DiagnosticLevel
    code: str
    message: str
    sheet_name: str | None = None
    cell_range: str | None = None
    row_number: int | None = None
    column_name: str | None = None
    source: str | None = None

    def render(self) -> str:
        """
        Возвращает человекочитаемую строку для логов и UI.

        :return: Сформированная строка сообщения.
        """
        parts: list[str] = [self.message]

        if self.sheet_name is not None:
            parts.append(f"sheet={self.sheet_name}")
        if self.cell_range is not None:
            parts.append(f"range={self.cell_range}")
        if self.row_number is not None:
            parts.append(f"row={self.row_number}")
        if self.column_name is not None:
            parts.append(f"column={self.column_name}")
        if self.source is not None:
            parts.append(f"source={self.source}")

        if len(parts) == 1:
            return parts[0]

        return f"{parts[0]} ({', '.join(parts[1:])})"

    @classmethod
    def from_operation_message(
        cls,
        message: Any,
        *,
        code: str = "legacy.message",
        source: str | None = None,
    ) -> "Diagnostic":
        """
        Преобразует старое сообщение `OperationMessage` в новый формат.

        :param message: Сообщение старой модели.
        :param code: Код диагностики.
        :param source: Источник сообщения.
        :return: Новый объект диагностики.
        """
        return cls(
            level=message.level,
            code=code,
            message=message.text,
            sheet_name=message.sheet_name,
            cell_range=message.cell_range,
            row_number=message.row_number,
            column_name=message.column_name,
            source=source,
        )


@dataclass(slots=True)
class DiagnosticCollector:
    """
    Накопитель диагностических сообщений.

    Коллектор упрощает код flow-ов и processor-ов: они могут добавлять
    сообщения по мере работы, а затем передавать готовый список в итоговый
    результат без ручной сборки промежуточных массивов.
    """

    diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(
        self,
        level: DiagnosticLevel,
        code: str,
        message: str,
        *,
        sheet_name: str | None = None,
        cell_range: str | None = None,
        row_number: int | None = None,
        column_name: str | None = None,
        source: str | None = None,
    ) -> Diagnostic:
        """
        Добавляет новое сообщение в коллекцию.

        :return: Созданный объект диагностики.
        """
        diagnostic = Diagnostic(
            level=level,
            code=code,
            message=message,
            sheet_name=sheet_name,
            cell_range=cell_range,
            row_number=row_number,
            column_name=column_name,
            source=source,
        )
        self.diagnostics.append(diagnostic)
        return diagnostic

    def info(self, code: str, message: str, **kwargs: object) -> Diagnostic:
        return self.add("info", code, message, **kwargs)

    def warning(self, code: str, message: str, **kwargs: object) -> Diagnostic:
        return self.add("warning", code, message, **kwargs)

    def error(self, code: str, message: str, **kwargs: object) -> Diagnostic:
        return self.add("error", code, message, **kwargs)

    def critical(self, code: str, message: str, **kwargs: object) -> Diagnostic:
        return self.add("critical", code, message, **kwargs)

    def extend(self, diagnostics: Iterable[Diagnostic]) -> None:
        """
        Добавляет в коллекцию набор уже готовых диагностик.
        """
        self.diagnostics.extend(diagnostics)

    @property
    def has_errors(self) -> bool:
        """
        Показывает, есть ли в коллекции ошибки любого уровня серьёзности.
        """
        return any(
            diagnostic.level in {"error", "critical"}
            for diagnostic in self.diagnostics
        )

    @property
    def has_critical_errors(self) -> bool:
        """
        Показывает, есть ли в коллекции критические ошибки.
        """
        return any(
            diagnostic.level == "critical"
            for diagnostic in self.diagnostics
        )
