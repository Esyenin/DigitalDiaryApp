"""
Настройки подключения к базе данных приложения.

Если параметры PostgreSQL не заполнены полностью, приложение автоматически
переключается на локальную SQLite-базу.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """
    Класс настроек приложения.

    Загружает переменные окружения из файла `.env` и умеет формировать URL
    подключения как для PostgreSQL, так и для резервной SQLite-базы.
    """
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_NAME: str | None = None
    SQLITE_DB_PATH: str = "digital_diary.db"

    # Получение из файла .env данных для DB
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env"
    )

    def has_postgresql_config(self) -> bool:
        """
        Проверяет, хватает ли настроек для подключения к PostgreSQL.

        :return: `True`, если все обязательные параметры PostgreSQL заданы,
            иначе `False`.
        """
        return all(
            value is not None and value != ""
            for value in (
                self.DB_USER,
                self.DB_PASSWORD,
                self.DB_HOST,
                self.DB_PORT,
                self.DB_NAME,
            )
        )

    def get_sqlite_db_url(self) -> str:
        """
        Формирует URL для локальной SQLite-базы.

        :return: Строка подключения SQLAlchemy к SQLite-файлу.
        """
        sqlite_path = BASE_DIR / self.SQLITE_DB_PATH
        return f"sqlite:///{sqlite_path.as_posix()}"

    def get_db_url(self) -> str:
        """
        Формирует URL подключения к базе данных.

        Если настройки PostgreSQL заданы полностью, возвращает URL
        PostgreSQL. Иначе возвращает URL локальной SQLite-базы.

        :return: Строка подключения SQLAlchemy.
        """
        if self.has_postgresql_config():
            return (
                f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )

        return self.get_sqlite_db_url()


# Объект класса для более простого взаимодействия с классом
settings = Settings()

if __name__ == "__main__":
    print("DB URL =>", settings.get_db_url())
    print("DB HOST =>", settings.DB_HOST)
