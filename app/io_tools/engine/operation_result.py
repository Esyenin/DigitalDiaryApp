"""
Общие результаты табличных операций.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.io_tools.engine.messages import OperationMessage


@dataclass(slots=True)
class TabularImportResult:
    """
    Хранит итог стандартного чтения табличного файла.

    Результат подходит для внутренних форматов приложения, когда нужно
    получить все считанные листы и параллельно сохранить предупреждения и
    ошибки без немедленного выброса исключения.
    """

    data: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    messages: list[OperationMessage] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        """
        Возвращает текстовые предупреждения.

        :return: Список warning-сообщений.
        """
        return [
            message.render()
            for message in self.messages
            if message.level == "warning"
        ]

    @property
    def errors(self) -> list[str]:
        """
        Возвращает текстовые ошибки.

        :return: Список error-сообщений.
        """
        return [
            message.render()
            for message in self.messages
            if message.level == "error"
        ]

    @property
    def is_valid(self) -> bool:
        """
        Показывает, есть ли в результате критические ошибки.

        :return: `True`, если ошибок нет.
        """
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
        """
        Добавляет предупреждение в результат операции.

        :param text: Текст warning-сообщения.
        :param sheet_name: Имя листа-источника.
        :param cell_range: Диапазон ячеек, если он известен.
        :param row_number: Номер строки внутри источника.
        :param column_name: Имя проблемной колонки.
        :return: `None`.
        """
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
        """
        Добавляет ошибку в результат операции.

        :param text: Текст error-сообщения.
        :param sheet_name: Имя листа-источника.
        :param cell_range: Диапазон ячеек, если он известен.
        :param row_number: Номер строки внутри источника.
        :param column_name: Имя проблемной колонки.
        :return: `None`.
        """
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
