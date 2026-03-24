"""
Файл для создания конфигурации пути к DB, основываясь на информации из .env
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from tomlkit.items import Null


class Settings(BaseSettings):
    """
    Класс настройки, автоматически подтягивает из .env данные
    """
    DB_USER: str = Null
    DB_PASSWORD: str = Null
    DB_HOST: str = Null
    DB_PORT: int = Null
    DB_NAME: str = Null

    # Получение из файла .env данных для DB
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    )

    def get_db_url(self) -> str:
        """
            Метод, формирующий url ссылку к базе данных
        """
        return (f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}")


# Объект класса для более простого взаимодействия с классом
settings = Settings()

if __name__ == "__main__":
    print("DB URL =>", settings.get_db_url())
    print("DB HOST =>", settings.DB_HOST)
