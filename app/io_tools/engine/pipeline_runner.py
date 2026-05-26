"""
Исполнитель последовательности шагов import-pipeline.

Runner знает только общий жизненный цикл шагов:

1. Нужно ли запускать шаг.
2. Следует ли остановиться после ошибки.
3. Как последовательно передать один контекст через несколько шагов.

Сам runner ничего не знает про XLSX, сущности дневника или прикладные схемы.
Благодаря этому его можно переиспользовать для любых сценариев табличной
обработки внутри `io_tools`.
"""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Protocol

from app.io_tools.engine.operation_context import ImportOperationContext


logger = logging.getLogger(__name__)


class PipelineStep(Protocol):
    """
    Контракт одного шага pipeline обработки.
    """

    def run(self, context: ImportOperationContext) -> None:
        """
        Изменяет переданный контекст операции.

        :param context: Контекст текущей операции.
        :return: `None`.
        """


class PipelineRunner:
    """
    Последовательно запускает шаги обработки на одном контексте.
    """

    def run(
        self,
        context: ImportOperationContext,
        steps: Iterable[PipelineStep],
    ) -> ImportOperationContext:
        """
        Выполняет набор шагов и возвращает изменённый контекст.

        :param context: Контекст операции.
        :param steps: Шаги pipeline в порядке выполнения.
        :return: Тот же контекст после выполнения шагов.
        """
        for step in steps:
            should_run = getattr(step, "should_run", None)
            if callable(should_run) and not should_run(context):
                logger.debug(
                    "PipelineRunner skipped step %s.",
                    step.__class__.__name__,
                )
                continue

            step.run(context)

            if getattr(step, "stop_on_error", False) and self._has_errors(context):
                logger.debug(
                    "PipelineRunner stopped after step %s because state contains errors.",
                    step.__class__.__name__,
                )
                break

        return context

    @staticmethod
    def _has_errors(context: ImportOperationContext) -> bool:
        """
        Проверяет, содержит ли текущее состояние ошибки.

        :param context: Контекст операции.
        :return: `True`, если ошибки найдены.
        """
        state = context.state
        if state.extracted_table is not None and state.extracted_table.errors:
            return True
        if state.import_result is not None and state.import_result.errors:
            return True
        if state.strict_result is not None and state.strict_result.errors:
            return True
        if state.strict_header_errors:
            return True

        return False
