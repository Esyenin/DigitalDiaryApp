"""
Use-case слой подготовки импортируемых табличных данных.

Файл описывает прикладные сценарии на уровне последовательностей шагов:

1. Прочитать диапазон.
2. Провести smart- или strict-подготовку.
3. Собрать итоговые payload-ы и диагностический результат.
4. Передать подготовленные данные следующему слою.

За счёт этого бизнес-последовательность живёт отдельно от низкоуровневого
чтения файла и отдельно от самих маленьких шагов pipeline.
"""
from __future__ import annotations

from collections.abc import Callable

from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.pipeline_runner import PipelineRunner
from app.io_tools.engine.processing_models import (
    DataProcessingResult,
    ImportProcessingResult,
    StrictImportResult,
)
from app.io_tools.engine.steps import (
    BuildHeaderBindingsStep,
    BuildProcessedRowsStep,
    BuildSmartImportResultStep,
    BuildStrictImportResultStep,
    NormalizeRowsStep,
    ResolveRowsStep,
    SmartImportAssembler,
    SmartReferenceResolver,
    SmartRowNormalizer,
    StrictImportAssembler,
    ValidateStrictHeadersStep,
)
from app.io_tools.engine.steps.base import BaseImportStep
from app.io_tools.formats.xlsx.readers.range_reader import SelectedRangeReader


class ReadSelectedRangeStep(BaseImportStep):
    """
    Шаг чтения выбранного XLSX-диапазона.
    """

    def __init__(self, range_reader: SelectedRangeReader) -> None:
        self.range_reader = range_reader

    def should_run(self, context: ImportOperationContext) -> bool:
        """
        Пропускает чтение, если таблица уже была подготовлена заранее.

        :param context: Контекст операции импорта.
        :return: `True`, если диапазон ещё нужно читать из файла.
        """
        return context.state.extracted_table is None

    def run(self, context: ImportOperationContext) -> None:
        context.state.extracted_table = self.range_reader.read(
            context.file_path,
            context.sheet_name or "",
            context.cell_range or "",
            entity_type=context.entity_type,
        )


class BuildDetailedSmartResultStep(BaseImportStep):
    """
    Шаг сборки подробного результата smart-обработки.
    """

    def __init__(self, assembler: SmartImportAssembler) -> None:
        self.assembler = assembler

    def run(self, context: ImportOperationContext) -> None:
        context.result = self.assembler.build_processing_result(context)


class PrepareSmartImportUseCase:
    """
    Use-case уровня "прочитать -> провалидировать -> подготовить payload".
    """

    def __init__(
        self,
        *,
        range_reader: SelectedRangeReader | None = None,
        row_normalizer: SmartRowNormalizer | None = None,
        reference_resolver: SmartReferenceResolver | None = None,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        self.range_reader = range_reader or SelectedRangeReader()
        self.row_normalizer = row_normalizer or SmartRowNormalizer()
        self.reference_resolver = reference_resolver or SmartReferenceResolver()
        self.pipeline_runner = pipeline_runner or PipelineRunner()
        self.assembler = SmartImportAssembler()

    def execute(self, context: ImportOperationContext) -> ImportProcessingResult:
        self.pipeline_runner.run(
            context,
            [
                ReadSelectedRangeStep(self.range_reader),
                NormalizeRowsStep(self.row_normalizer),
                ResolveRowsStep(self.reference_resolver),
                BuildSmartImportResultStep(self.assembler),
            ],
        )
        assert isinstance(context.result, ImportProcessingResult)
        return context.result


class PrepareDetailedSmartImportUseCase:
    """
    Use-case уровня "прочитать -> провалидировать -> подготовить payload -> показать трассировку".
    """

    def __init__(
        self,
        *,
        range_reader: SelectedRangeReader | None = None,
        row_normalizer: SmartRowNormalizer | None = None,
        reference_resolver: SmartReferenceResolver | None = None,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        self.range_reader = range_reader or SelectedRangeReader()
        self.row_normalizer = row_normalizer or SmartRowNormalizer()
        self.reference_resolver = reference_resolver or SmartReferenceResolver()
        self.pipeline_runner = pipeline_runner or PipelineRunner()
        self.assembler = SmartImportAssembler()

    def execute(self, context: ImportOperationContext) -> DataProcessingResult:
        self.pipeline_runner.run(
            context,
            [
                ReadSelectedRangeStep(self.range_reader),
                BuildHeaderBindingsStep(self.assembler, self.row_normalizer),
                NormalizeRowsStep(self.row_normalizer),
                ResolveRowsStep(self.reference_resolver),
                BuildSmartImportResultStep(self.assembler),
                BuildProcessedRowsStep(self.assembler),
                BuildDetailedSmartResultStep(self.assembler),
            ],
        )
        assert isinstance(context.result, DataProcessingResult)
        return context.result


class PrepareStrictImportUseCase:
    """
    Use-case уровня "прочитать -> строго провалидировать -> подготовить payload".
    """

    def __init__(
        self,
        *,
        range_reader: SelectedRangeReader | None = None,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        self.range_reader = range_reader or SelectedRangeReader()
        self.pipeline_runner = pipeline_runner or PipelineRunner()
        self.assembler = StrictImportAssembler()

    def execute(self, context: ImportOperationContext) -> StrictImportResult:
        self.pipeline_runner.run(
            context,
            [
                ReadSelectedRangeStep(self.range_reader),
                ValidateStrictHeadersStep(),
                BuildStrictImportResultStep(self.assembler),
            ],
        )
        assert isinstance(context.result, StrictImportResult)
        return context.result


class DeliverPreparedPayloadsUseCase:
    """
    Use-case передачи уже подготовленных payload-ов следующему слою.
    """

    def execute(
        self,
        prepared_payloads: list[dict[str, object]],
        consumer: Callable[[list[dict[str, object]]], object],
    ) -> object:
        return consumer(prepared_payloads)
