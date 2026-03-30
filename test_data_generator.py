# test_data_generator.py
"""
Генератор тестовых данных для Digital Diary
20 студентов, 10 уроков, 2 расписания
"""

import random
from datetime import date, time

from app.models.group import GroupCRUD
from app.models.schedule import ScheduleCRUD
from app.models.schedule_group_link import ScheduleGroupLinkCRUD
from app.models.student import StudentCRUD
from app.models.lesson import LessonCRUD
from app.models.attendance import AttendanceCRUD
from app.models.mark import MarkCRUD
from app.models.comment import CommentCRUD


def generate_test_data():
    """Генерация всех тестовых данных"""

    print("=" * 60)
    print("🚀 ГЕНЕРАЦИЯ ТЕСТОВЫХ ДАННЫХ")
    print("=" * 60)

    # ========== 1. СОЗДАЁМ ГРУППЫ ==========
    print("\n📚 1. Создание групп...")
    group1 = GroupCRUD.crud_groups('create', name='ИУ7-11Б', speciality='Информатика и вычислительная техника')
    group2 = GroupCRUD.crud_groups('create', name='ИУ7-12Б', speciality='Информатика и вычислительная техника')
    print(f"   ✅ Группа 1: {group1.name} (ID={group1.id})")
    print(f"   ✅ Группа 2: {group2.name} (ID={group2.id})")

    # ========== 2. СОЗДАЁМ РАСПИСАНИЯ (2 разных) ==========
    print("\n📅 2. Создание расписаний...")
    schedule1 = ScheduleCRUD.crud_schedules('create',
                                            odd_or_even='even',
                                            schedule_type='lecture',
                                            is_assessment=False,
                                            day='Monday',
                                            time=time(9, 0))
    schedule2 = ScheduleCRUD.crud_schedules('create',
                                            odd_or_even='odd',
                                            schedule_type='seminar',
                                            is_assessment=True,  # Оценочное!
                                            day='Wednesday',
                                            time=time(10, 30))
    print(f"   ✅ Расписание 1: {schedule1.day} {schedule1.type} (ID={schedule1.id})")
    print(f"   ✅ Расписание 2: {schedule2.day} {schedule2.type} (ID={schedule2.id}) [Оценочное]")

    # ========== 3. СВЯЗЫВАЕМ ГРУППЫ С РАСПИСАНИЯМИ ==========
    print("\n🔗 3. Связь групп с расписаниями...")
    for group in [group1, group2]:
        for schedule in [schedule1, schedule2]:
            link = ScheduleGroupLinkCRUD.crud_schedule_group_links('create',
                                                                   group_id=group.id,
                                                                   schedule_id=schedule.id)
            print(f"   ✅ {group.name} ↔ {schedule.day} (Link ID={link.id})")

    # ========== 4. СОЗДАЁМ 20 СТУДЕНТОВ ==========
    print("\n👨‍🎓 4. Создание 20 студентов...")
    surnames = ['Иванов', 'Петров', 'Сидоров', 'Смирнов', 'Кузнецов',
                'Попов', 'Васильев', 'Михайлов', 'Новиков', 'Фёдоров',
                'Морозов', 'Волков', 'Алексеев', 'Лебедев', 'Семёнов',
                'Егоров', 'Павлов', 'Козлов', 'Степанов', 'Николаев']
    first_names = ['Александр', 'Дмитрий', 'Максим', 'Сергей', 'Андрей',
                   'Алексей', 'Артём', 'Илья', 'Кирилл', 'Михаил',
                   'Никита', 'Матвей', 'Роман', 'Егор', 'Арсений',
                   'Иван', 'Денис', 'Евгений', 'Тимофей', 'Владимир']

    students = []
    for i in range(20):
        # Распределяем по группам: 10 в первой, 10 во второй
        group = group1 if i < 10 else group2
        student = StudentCRUD.crud_students('create',
                                            group_id=group.id,
                                            surname=surnames[i],
                                            first_name=first_names[i],
                                            patronymic='Александрович',
                                            personal_data=f'{i + 1:02d}/{2024}',
                                            bmstu_email=f'{surnames[i].lower()}{i + 1}@bmstu.ru')
        students.append(student)
        print(f"   ✅ Студент {i + 1}: {student.surname} {student.first_name} (ID={student.id}, Группа={group.name})")

    # ========== 5. СОЗДАЁМ 10 УРОКОВ ==========
    print("\n📖 5. Создание 10 уроков...")
    topics = [
        'Введение в базы данных',
        'Реляционная модель данных',
        'SQL: основы запросов',
        'Нормализация баз данных',
        'Индексы и оптимизация',
        'Транзакции и блокировки',
        'Проектирование БД',
        'NoSQL базы данных',
        'ORM и SQLAlchemy',
        'Миграции и версионирование'
    ]

    lessons = []
    for i in range(10):
        # Чередую расписания: 5 уроков по расписанию 1, 5 по расписанию 2
        schedule = schedule1 if i < 5 else schedule2
        lesson_date = date(2025, 1, 15 + i)  # 15-24 января 2025

        lesson = LessonCRUD.crud_lessons('create',
                                         schedule_id=schedule.id,
                                         topic=topics[i],
                                         date=lesson_date)
        lessons.append(lesson)

        # Помечаем, является ли урок оценочным
        is_assessment = schedule.is_assessment
        assessment_mark = " [Оценочный]" if is_assessment else ""
        print(f"   ✅ Урок {i + 1}: {lesson.topic} (ID={lesson.id}, Дата={lesson_date}){assessment_mark}")

    # ========== 6. СОЗДАЁМ ПОСЕЩАЕМОСТЬ (Attendance) ==========
    print("\n✅ 6. Создание посещаемости...")
    attendances = []
    for student in students:
        for lesson in lessons:
            # 90% посещаемость
            is_visited = random.random() < 0.9
            attendance = AttendanceCRUD.crud_attendances('create',
                                                         student_id=student.id,
                                                         lesson_id=lesson.id,
                                                         is_visited=is_visited)
            attendances.append(attendance)

    visited_count = sum(1 for a in attendances if a.is_visited)
    print(f"   ✅ Создано посещаемостей: {len(attendances)}")
    print(f"   📊 Посещено: {visited_count} ({visited_count / len(attendances) * 100:.1f}%)")
    print(
        f"   📊 Пропущено: {len(attendances) - visited_count} ({(len(attendances) - visited_count) / len(attendances) * 100:.1f}%)")

    # ========== 7. СОЗДАЁМ ОЦЕНКИ (Mark) ==========
    print("\n📊 7. Создание оценок (только для оценочных уроков)...")
    marks = []
    for student in students:
        for lesson in lessons:
            # Проверяем, является ли урок оценочным (расписание 2)
            if lesson.schedule_id == schedule2.id:
                # Оценка только если студент посетил урок
                attendance = next((a for a in attendances if a.student_id == student.id and a.lesson_id == lesson.id),
                                  None)
                if attendance and attendance.is_visited:
                    # Случайная оценка от 3 до 5
                    mark_value = random.choice([3, 4, 4, 5, 5])  # Больше 4 и 5
                    mark = MarkCRUD.crud_marks('create',
                                               student_id=student.id,
                                               lesson_id=lesson.id,
                                               data=mark_value)
                    marks.append(mark)

    print(f"   ✅ Создано оценок: {len(marks)}")
    if marks:
        avg_mark = sum(m.data for m in marks) / len(marks)
        print(f"   📊 Средняя оценка: {avg_mark:.2f}")
        print(
            f"   📊 Распределение: 3={sum(1 for m in marks if m.data == 3)}, 4={sum(1 for m in marks if m.data == 4)}, 5={sum(1 for m in marks if m.data == 5)}")

    # ========== 8. СОЗДАЁМ КОММЕНТАРИИ (20% вероятность) ==========
    print("\n💬 8. Создание комментариев (20% вероятность)...")
    comments = []
    comment_templates = [
        'Отличная работа!',
        'Хорошее понимание материала',
        'Рекомендую повторить тему',
        'Активная работа на занятии',
        'Есть прогресс в изучении',
        'Стоит уделить больше внимания практике',
        'Превосходный результат',
        'Молодец, так держать!',
        'Нужно подтянуть теорию',
        'Отлично справился с заданием'
    ]

    for student in students:
        for lesson in lessons:
            # 20% вероятность комментария
            if random.random() < 0.2:
                comment_text = random.choice(comment_templates)
                comment = CommentCRUD.crud_comments('create',
                                                    student_id=student.id,
                                                    lesson_id=lesson.id,
                                                    data=comment_text)
                comments.append(comment)

    print(f"   ✅ Создано комментариев: {len(comments)}")
    print(f"   📊 Вероятность: {len(comments) / (len(students) * len(lessons)) * 100:.1f}%")

    # ========== ИТОГИ ==========
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ГЕНЕРАЦИИ")
    print("=" * 60)
    print(f"   📚 Группы: 2")
    print(f"   📅 Расписания: 2")
    print(f"   👨‍🎓 Студенты: {len(students)}")
    print(f"   📖 Уроки: {len(lessons)}")
    print(f"   ✅ Посещаемости: {len(attendances)}")
    print(f"   📊 Оценки: {len(marks)}")
    print(f"   💬 Комментарии: {len(comments)}")
    print("=" * 60)
    print("✅ ГЕНЕРАЦИЯ ЗАВЕРШЕНА!")
    print("=" * 60)

    return {
        'groups': [group1, group2],
        'schedules': [schedule1, schedule2],
        'students': students,
        'lessons': lessons,
        'attendances': attendances,
        'marks': marks,
        'comments': comments
    }


if __name__ == '__main__':
    generate_test_data()