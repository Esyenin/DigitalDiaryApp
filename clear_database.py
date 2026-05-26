from sqlalchemy import create_engine

from config import settings
from app.models import Base


def clear_database() -> None:
    db_url = settings.get_db_url()

    print(f"Database URL: {db_url}")
    print("Dropping all tables...")

    engine = create_engine(db_url)

    try:
        Base.metadata.drop_all(bind=engine)
        print("Creating all tables...")
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()

    print("Database cleared successfully.")


if __name__ == "__main__":
    clear_database()
