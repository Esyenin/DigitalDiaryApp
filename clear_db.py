# clear_db.py
"""Очистка базы данных"""

# ВАЖНО: Импортируем ВСЕ модели, чтобы они зарегистрировались в Base.metadata
from app.models import group, schedule, schedule_group_link, student, lesson, attendance, mark, comment
from app.database import drop_tables, create_tables

print("🧹 Очистка базы данных...")
drop_tables()
create_tables()
print("✅ БД очищена")