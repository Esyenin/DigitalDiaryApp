"""
Настройка файлового логирования приложения.

Модуль содержит функцию, которую нужно вызывать при старте программы, когда
приложению уже известно, куда складывать файлы логов и с какого уровня
начинать запись.
"""
from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path


DEFAULT_LOGS_DIR = "logs"
LOG_FILE_DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"
LOG_RECORD_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_RECORD_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s"
)
_PROJECT_FILE_HANDLER_FLAG = "_digital_diary_file_handler"


def _normalize_level(level: int | str) -> tuple[int, str]:
    """
    Приводит уровень логирования к числу и строковому имени.

    :param level: Уровень логирования в виде числа из модуля `logging` или
        строкового имени уровня.
    :return: Кортеж из числового уровня и его имени в верхнем регистре.
    :raises ValueError: Если строковый уровень не поддерживается модулем
        `logging`.
    """
    if isinstance(level, int):
        level_number = level
        level_name = logging.getLevelName(level_number)
        if not isinstance(level_name, str):
            level_name = str(level_number)

        return level_number, level_name.upper()

    level_name = level.upper()
    level_number = logging.getLevelName(level_name)
    if not isinstance(level_number, int):
        raise ValueError(f"Неизвестный уровень логирования: {level}.")

    return level_number, level_name


def build_log_file_path(
    logs_dir: str | Path = DEFAULT_LOGS_DIR,
    level: int | str = logging.INFO,
    created_at: datetime | None = None,
) -> Path:
    """
    Создает путь к файлу лога в принятом формате имени.

    Имя файла строится как `ДАТА_ВРЕМЯ_УРОВЕНЬ.log`. Время в имени файла
    указывается до секунд, чтобы путь оставался безопасным для Windows и Linux.

    :param logs_dir: Каталог, в котором должен лежать файл лога.
    :param level: Уровень логирования, который нужно указать в имени файла.
    :param created_at: Дата и время для имени файла. Если параметр не передан,
        используется текущее локальное время.
    :return: Путь к файлу лога.
    :raises ValueError: Если передан неизвестный строковый уровень.
    """
    _, level_name = _normalize_level(level)
    timestamp = (created_at or datetime.now()).strftime(LOG_FILE_DATE_FORMAT)

    return Path(logs_dir) / f"{timestamp}_{level_name}.log"


def configure_file_logging(
    level: int | str = logging.INFO,
    logs_dir: str | Path = DEFAULT_LOGS_DIR,
    logger_name: str | None = None,
) -> Path:
    """
    Настраивает запись логов в файл.

    Файл создается в формате имени `ДАТА_ВРЕМЯ_УРОВЕНЬ.log`. Записи внутри
    файла содержат дату и время до миллисекунд, уровень сообщения, имя logger
    и текст сообщения.

    :param level: Минимальный уровень сообщений, которые будут попадать в файл.
    :param logs_dir: Каталог для файлов логов. Если каталога нет, он будет
        создан.
    :param logger_name: Имя logger, который нужно настроить. Если передан
        `None`, настраивается корневой logger приложения.
    :return: Путь к созданному файлу лога.
    :raises ValueError: Если передан неизвестный строковый уровень.
    """
    level_number, _ = _normalize_level(level)
    log_file_path = build_log_file_path(logs_dir=logs_dir, level=level)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level_number)

    for handler in tuple(logger.handlers):
        if getattr(handler, _PROJECT_FILE_HANDLER_FLAG, False):
            logger.removeHandler(handler)
            handler.close()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    setattr(file_handler, _PROJECT_FILE_HANDLER_FLAG, True)
    file_handler.setLevel(level_number)
    file_handler.setFormatter(
        logging.Formatter(
            fmt=LOG_RECORD_FORMAT,
            datefmt=LOG_RECORD_DATE_FORMAT,
        )
    )

    logger.addHandler(file_handler)

    if logger_name is not None:
        logger.propagate = False

    return log_file_path
