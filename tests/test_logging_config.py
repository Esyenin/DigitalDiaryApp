"""
Тесты настройки файлового логирования.
"""
from datetime import datetime
import logging
import re

from app.logging_config import build_log_file_path, configure_file_logging


def test_build_log_file_path_uses_date_time_and_level(tmp_path):
    """
    Проверяет формат имени файла лога.

    :param tmp_path: Временный каталог pytest.
    :return: `None`. Тест падает, если имя файла не содержит дату, время до
        секунд и уровень логирования.
    """
    log_file_path = build_log_file_path(
        logs_dir=tmp_path,
        level=logging.WARNING,
        created_at=datetime(2026, 5, 9, 14, 30, 45, 123000),
    )

    assert log_file_path.name == "2026-05-09_14-30-45_WARNING.log"


def test_configure_file_logging_writes_milliseconds(tmp_path):
    """
    Проверяет формат времени внутри файла лога.

    :param tmp_path: Временный каталог pytest.
    :return: `None`. Тест падает, если запись в файле не содержит
        миллисекунды.
    """
    logger_name = "tests.logging_config"
    log_file_path = configure_file_logging(
        level="INFO",
        logs_dir=tmp_path,
        logger_name=logger_name,
    )
    logger = logging.getLogger(logger_name)

    logger.info("message")
    for handler in logger.handlers:
        handler.flush()

    log_content = log_file_path.read_text(encoding="utf-8")

    assert re.search(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}",
        log_content,
    )
    assert "INFO | tests.logging_config | message" in log_content
