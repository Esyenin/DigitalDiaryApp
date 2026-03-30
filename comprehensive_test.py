# comprehensive_test.py
"""
Комплексный тест всей системы Digital Diary
Проверяет CRUD, связи, фильтрацию, целостность данных
"""

import sys
from datetime import date, time

# ========== ЦВЕТА ДЛЯ ВЫВОДА ==========
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")
def info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

# ========== СЧЁТЧИКИ ==========
tests_passed = 0
tests_failed = 0
test_results = []

def test(condition, name, details=""):
    global tests_passed, tests_failed
    if condition:
        success(f"{name}")
        tests_passed += 1
        test_results.append(("PASS", name))
    else:
        error(f"{name}")
        if details:
            print(f"   {Colors.RED}Детали: {details}{Colors.END}")
        tests_failed += 1
        test_results.append(("FAIL", name, details))

# ========== ИМПОРТЫ ==========
print("=" * 80)
print("🧪 КОМПЛЕКСНЫЙ ТЕСТ DIGITAL DIARY")
print("=" * 80)

try:
    from app.models.group import Group, GroupCRUD
    from app.models.schedule import Schedule, ScheduleCRUD
    from app.models.schedule_group_link import ScheduleGroupLink, ScheduleGroupLinkCRUD
    from app.models.student import Student, StudentCRUD
    from app.models.lesson import Lesson, LessonCRUD
    from app.models.attendance import Attendance, AttendanceCRUD
    from app.models.mark import Mark, MarkCRUD
    from app.models.comment import Comment, CommentCRUD
    from app.database import Base, engine, drop_tables, create_tables
    success("Все модели импортированы")
except Exception as e:
    error(f"Ошибка импорта: {e}")
    sys.exit(1)

# ========== ОЧИСТКА БД ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 1: ОЧИСТКА БАЗЫ ДАННЫХ")
print("=" * 80)

try:
    drop_tables()
    create_tables()
    success("БД очищена и таблицы созданы")
except Exception as e:
    error(f"Ошибка очистки БД: {e}")
    sys.exit(1)

# ========== ТЕСТ 1: ГРУППЫ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 2: ТЕСТ ГРУПП")
print("=" * 80)

group1 = GroupCRUD.crud_groups('create', name='ИУ7-11Б', speciality='ИВТ')
group2 = GroupCRUD.crud_groups('create', name='ИУ7-12Б', speciality='ИВТ')

test(group1.id is not None, "Создание группы 1", f"ID={group1.id}")
test(group2.id is not None, "Создание группы 2", f"ID={group2.id}")

all_groups = GroupCRUD.crud_groups('read')
test(len(all_groups) == 2, f"Количество групп = 2", f"Фактически: {len(all_groups)}")

group1_read = GroupCRUD.crud_groups('read', group_id=group1.id)
test(group1_read.name == 'ИУ7-11Б', "Чтение группы по ID", f"Название: {group1_read.name}")

# ========== ТЕСТ 2: РАСПИСАНИЯ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 3: ТЕСТ РАСПИСАНИЙ")
print("=" * 80)

schedule1 = ScheduleCRUD.crud_schedules('create', odd_or_even='even', schedule_type='lecture',
                                         is_assessment=False, day='Monday', time=time(9, 0))
schedule2 = ScheduleCRUD.crud_schedules('create', odd_or_even='odd', schedule_type='seminar',
                                         is_assessment=True, day='Wednesday', time=time(10, 30))

test(schedule1.id is not None, "Создание расписания 1", f"ID={schedule1.id}")
test(schedule2.is_assessment == True, "Оценочное расписание", f"is_assessment={schedule2.is_assessment}")

all_schedules = ScheduleCRUD.crud_schedules('read')
test(len(all_schedules) == 2, f"Количество расписаний = 2", f"Фактически: {len(all_schedules)}")

# ========== ТЕСТ 3: СВЯЗИ ГРУППА-РАСПИСАНИЕ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 4: ТЕСТ СВЯЗЕЙ ГРУППА-РАСПИСАНИЕ")
print("=" * 80)

link1 = ScheduleGroupLinkCRUD.crud_schedule_group_links('create', group_id=group1.id, schedule_id=schedule1.id)
link2 = ScheduleGroupLinkCRUD.crud_schedule_group_links('create', group_id=group1.id, schedule_id=schedule2.id)
link3 = ScheduleGroupLinkCRUD.crud_schedule_group_links('create', group_id=group2.id, schedule_id=schedule1.id)
link4 = ScheduleGroupLinkCRUD.crud_schedule_group_links('create', group_id=group2.id, schedule_id=schedule2.id)

test(link1.id is not None, "Создание связи 1", f"ID={link1.id}")
test(len(ScheduleGroupLinkCRUD.crud_schedule_group_links('read')) == 4, "Количество связей = 4")

# ========== ТЕСТ 4: СТУДЕНТЫ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 5: ТЕСТ СТУДЕНТОВ")
print("=" * 80)

students = []
for i in range(20):
    group = group1 if i < 10 else group2
    # ✅ ИСПРАВЛЕНО: добавлены personal_data и bmstu_email
    student = StudentCRUD.crud_students('create',
                                         group_id=group.id,
                                         surname=f'Фамилия{i+1}',
                                         first_name=f'Имя{i+1}',
                                         patronymic='Отчество',
                                         personal_data=f'2024{i+1:03d}',
                                         bmstu_email=f'student{i+1}@bmstu.ru')
    students.append(student)

test(len(students) == 20, "Создано 20 студентов", f"Фактически: {len(students)}")

group1_students = [s for s in students if s.group_id == group1.id]
group2_students = [s for s in students if s.group_id == group2.id]
test(len(group1_students) == 10, "Студентов в группе 1 = 10", f"Фактически: {len(group1_students)}")
test(len(group2_students) == 10, "Студентов в группе 2 = 10", f"Фактически: {len(group2_students)}")

# 🔴 ПРОВЕРКА ФИЛЬТРАЦИИ READ
student1_all = StudentCRUD.crud_students('read')
student1_by_id = StudentCRUD.crud_students('read', student_id=students[0].id)
test(student1_by_id is not None, "Чтение студента по ID", f"Все студенты: {len(student1_all)}")

# 🔴 ПРОВЕРКА personal_data и bmstu_email
test(students[0].personal_data == '2024001', "personal_data у студента 1", f"Фактически: {students[0].personal_data}")
test(students[0].bmstu_email == 'student1@bmstu.ru', "bmstu_email у студента 1", f"Фактически: {students[0].bmstu_email}")

# Проверка уникальности personal_data
personal_data_list = [s.personal_data for s in students if s.personal_data]
test(len(personal_data_list) == len(set(personal_data_list)), "Уникальность personal_data", f"Дубликатов: {len(personal_data_list) - len(set(personal_data_list))}")

# ========== ТЕСТ 5: УРОКИ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 6: ТЕСТ УРОКОВ")
print("=" * 80)

lessons = []
for i in range(10):
    schedule = schedule1 if i < 5 else schedule2  # 5 обычных + 5 оценочных
    lesson = LessonCRUD.crud_lessons('create', schedule_id=schedule.id, topic=f'Тема {i+1}',
                                      date=date(2025, 1, 15+i))
    lessons.append(lesson)

test(len(lessons) == 10, "Создано 10 уроков", f"Фактически: {len(lessons)}")

assessment_lessons = [l for l in lessons if l.schedule_id == schedule2.id]
test(len(assessment_lessons) == 5, "Оценочных уроков = 5", f"Фактически: {len(assessment_lessons)}")

# ========== ТЕСТ 6: ПОСЕЩАЕМОСТЬ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 7: ТЕСТ ПОСЕЩАЕМОСТИ")
print("=" * 80)

attendances = []
for student in students:
    for lesson in lessons:
        att = AttendanceCRUD.crud_attendances('create', student_id=student.id, lesson_id=lesson.id,
                                               is_visited=True)
        attendances.append(att)

test(len(attendances) == 200, "Создано 200 посещаемостей (20×10)", f"Фактически: {len(attendances)}")

# 🔴 ПРОВЕРКА ФИЛЬТРАЦИИ ПО СТУДЕНТУ
student1_attendances = AttendanceCRUD.crud_attendances('read', student_id=students[0].id)
test(len(student1_attendances) == 10, f"Посещаемость студента 1 = 10",
     f"Фактически: {len(student1_attendances)} ⚠️  АНОМАЛИЯ!" if len(student1_attendances) != 10 else "")

# 🔴 ПРОВЕРКА ФИЛЬТРАЦИИ ПО УРОКУ
lesson1_attendances = AttendanceCRUD.crud_attendances('read', lesson_id=lessons[0].id)
test(len(lesson1_attendances) == 20, f"Посещаемость урока 1 = 20",
     f"Фактически: {len(lesson1_attendances)} ⚠️  АНОМАЛИЯ!" if len(lesson1_attendances) != 20 else "")

# ========== ТЕСТ 7: ОЦЕНКИ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 8: ТЕСТ ОЦЕНОК")
print("=" * 80)

marks = []
for student in students:
    for lesson in assessment_lessons:  # Только оценочные уроки
        mark = MarkCRUD.crud_marks('create', student_id=student.id, lesson_id=lesson.id, data=4)
        marks.append(mark)

test(len(marks) == 100, "Создано 100 оценок (20×5)", f"Фактически: {len(marks)}")

# 🔴 ПРОВЕРКА ФИЛЬТРАЦИИ ПО СТУДЕНТУ
student1_marks = MarkCRUD.crud_marks('read', student_id=students[0].id)
test(len(student1_marks) == 5, f"Оценки студента 1 = 5",
     f"Фактически: {len(student1_marks)} ⚠️  АНОМАЛИЯ!" if len(student1_marks) != 5 else "")

# 🔴 ПРОВЕРКА ФИЛЬТРАЦИИ ПО УРОКУ
lesson6_marks = MarkCRUD.crud_marks('read', lesson_id=assessment_lessons[0].id)
test(len(lesson6_marks) == 20, f"Оценки урока 6 = 20",
     f"Фактически: {len(lesson6_marks)} ⚠️  АНОМАЛИЯ!" if len(lesson6_marks) != 20 else "")

# ========== ТЕСТ 8: КОММЕНТАРИИ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 9: ТЕСТ КОММЕНТАРИЕВ")
print("=" * 80)

comments = []
for i, student in enumerate(students):
    for j, lesson in enumerate(lessons):
        if (i + j) % 5 == 0:  # ~20% вероятность
            comment = CommentCRUD.crud_comments('create', student_id=student.id, lesson_id=lesson.id,
                                                 data=f'Комментарий {i}-{j}')
            comments.append(comment)

info(f"Создано комментариев: {len(comments)} (около 20% от 200)")

# 🔴 ПРОВЕРКА ФИЛЬТРАЦИИ ПО СТУДЕНТУ (ГЛАВНЫЙ ТЕСТ!)
student1_comments = CommentCRUD.crud_comments('read', student_id=students[0].id)
expected_comments = len([c for c in comments if c.student_id == students[0].id])
test(len(student1_comments) == expected_comments,
     f"Комментарии студента 1 = {expected_comments}",
     f"Фактически: {len(student1_comments)} ⚠️  АНОМАЛИЯ!" if len(student1_comments) != expected_comments else "")

# 🔴 ПРОВЕРКА ФИЛЬТРАЦИИ ПО УРОКУ
lesson1_comments = CommentCRUD.crud_comments('read', lesson_id=lessons[0].id)
expected_lesson_comments = len([c for c in comments if c.lesson_id == lessons[0].id])
test(len(lesson1_comments) == expected_lesson_comments,
     f"Комментарии урока 1 = {expected_lesson_comments}",
     f"Фактически: {len(lesson1_comments)} ⚠️  АНОМАЛИЯ!" if len(lesson1_comments) != expected_lesson_comments else "")

# ========== ТЕСТ 9: КАСКАДНОЕ УДАЛЕНИЕ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 10: ТЕСТ КАСКАДНОГО УДАЛЕНИЯ")
print("=" * 80)

# Создаём тестового студента с данными
test_student = StudentCRUD.crud_students('create', group_id=group1.id, surname='Тестов',
                                          first_name='Тест', patronymic='Тестович',
                                          personal_data='2024999', bmstu_email='testov@bmstu.ru')
test_att = AttendanceCRUD.crud_attendances('create', student_id=test_student.id, lesson_id=lessons[0].id, is_visited=True)
test_mark = MarkCRUD.crud_marks('create', student_id=test_student.id, lesson_id=lessons[0].id, data=5)
test_comment = CommentCRUD.crud_comments('create', student_id=test_student.id, lesson_id=lessons[0].id, data='Тест')

before_delete_att = len(AttendanceCRUD.crud_attendances('read', student_id=test_student.id))
before_delete_mark = len(MarkCRUD.crud_marks('read', student_id=test_student.id))
before_delete_comment = len(CommentCRUD.crud_comments('read', student_id=test_student.id))

StudentCRUD.crud_students('delete', student_id=test_student.id)

after_delete_att = len(AttendanceCRUD.crud_attendances('read', student_id=test_student.id))
after_delete_mark = len(MarkCRUD.crud_marks('read', student_id=test_student.id))
after_delete_comment = len(CommentCRUD.crud_comments('read', student_id=test_student.id))

test(after_delete_att == 0, "Каскадное удаление: посещаемость", f"До: {before_delete_att}, После: {after_delete_att}")
test(after_delete_mark == 0, "Каскадное удаление: оценки", f"До: {before_delete_mark}, После: {after_delete_mark}")
test(after_delete_comment == 0, "Каскадное удаление: комментарии", f"До: {before_delete_comment}, После: {after_delete_comment}")

# ========== ТЕСТ 10: ЦЕЛОСТНОСТЬ ДАННЫХ ==========
print("\n" + "=" * 80)
print("📋 ЭТАП 11: ПРОВЕРКА ЦЕЛОСТНОСТИ ДАННЫХ")
print("=" * 80)

all_students = StudentCRUD.crud_students('read')
all_marks = MarkCRUD.crud_marks('read')
all_attendances = AttendanceCRUD.crud_attendances('read')
all_comments = CommentCRUD.crud_comments('read')

test(len(all_students) == 20, "Всего студентов = 20", f"Фактически: {len(all_students)}")
test(len(all_attendances) == 200, "Всего посещаемостей = 200", f"Фактически: {len(all_attendances)}")
test(len(all_marks) == 100, "Всего оценок = 100", f"Фактически: {len(all_marks)}")

# Проверка: у каждого студента есть personal_data
students_with_personal = len([s for s in all_students if s.personal_data])
test(students_with_personal == 20, "У всех студентов есть personal_data", f"Фактически: {students_with_personal}/20")

# Проверка: у каждого студента есть bmstu_email
students_with_email = len([s for s in all_students if s.bmstu_email])
test(students_with_email == 20, "У всех студентов есть bmstu_email", f"Фактически: {students_with_email}/20")

# Проверка: у каждого студента максимум 10 посещаемостей
for student in all_students:
    att = AttendanceCRUD.crud_attendances('read', student_id=student.id)
    test(len(att) <= 10, f"Студент {student.id}: посещаемостей <= 10",
         f"Фактически: {len(att)} ⚠️  АНОМАЛИЯ!" if len(att) > 10 else "")

# Проверка: у каждого студента максимум 5 оценок (только оценочные уроки)
for student in all_students:
    marks = MarkCRUD.crud_marks('read', student_id=student.id)
    test(len(marks) <= 5, f"Студент {student.id}: оценок <= 5",
         f"Фактически: {len(marks)} ⚠️  АНОМАЛИЯ!" if len(marks) > 5 else "")

# ========== ИТОГИ ==========
print("\n" + "=" * 80)
print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
print("=" * 80)

total_tests = tests_passed + tests_failed
pass_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0

print(f"\nВсего тестов: {total_tests}")
print(f"{Colors.GREEN}Пройдено: {tests_passed}{Colors.END}")
print(f"{Colors.RED}Провалено: {tests_failed}{Colors.END}")
print(f"Успешность: {pass_rate:.1f}%")

if tests_failed == 0:
    print(f"\n{Colors.GREEN}🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система работает корректно!{Colors.END}")
else:
    print(f"\n{Colors.RED}⚠️  ОБНАРУЖЕНЫ ПРОБЛЕМЫ! Проверьте файлы выше.{Colors.END}")
    print(f"\nСписок проблем:")
    for result in test_results:
        if result[0] == "FAIL":
            print(f"  ❌ {result[1]}")
            if len(result) > 2:
                print(f"     {result[2]}")

print("\n" + "=" * 80)