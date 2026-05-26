"""
Алиасы и нормализация заголовков табличных форматов.
"""
from __future__ import annotations

import re


CanonicalEntityType = str
ReferenceKey = str


DIRECT_FIELD_ALIASES: dict[CanonicalEntityType, dict[str, set[str]]] = {
    "groups": {
        "id": {"id", "group id", "group_id", "id группы"},
        "name": {
            "name",
            "group",
            "groups",
            "group name",
            "группа",
            "группы",
            "название группы",
        },
        "speciality": {
            "speciality",
            "specialities",
            "специальность",
            "специальности",
        },
    },

    "schedules": {
        "id": {"id", "schedule id", "schedule_id", "id расписания"},
        "odd_or_even": {
            "odd_or_even",
            "odd or even",
            "четность",
            "нечетность",
            "чётность",
        },
        "type": {
            "type",
            "тип",
            "тип занятия",
        },
        "is_assessment": {
            "is_assessment",
            "assessment",
            "аттестация",
            "контроль",
            "контрольная",
            "контрольная точка",
        },
        "day": {
            "day",
            "день",
            "день недели",
        },
        "time": {
            "time",
            "время",
            "время занятия",
            "пара",
        },
    },

    "students": {
        "id": {"id", "student id", "student_id", "id студента"},
        "group_id": {
            "group id",
            "group_id",
            "id группы",
        },
        "surname": {
            "surname",
            "last name",
            "lastname",
            "фамилия",
            "фамилии",
            "фамилия студента",
        },
        "first_name": {
            "first name",
            "firstname",
            "first_name",
            "name",
            "имя",
            "имена",
            "имя студента",
        },
        "patronymic": {
            "patronymic",
            "middle name",
            "middlename",
            "отчество",
            "отчества",
            "отчество студента",
        },
        "personal_data": {
            "personal data",
            "personal_data",
            "личное дело",
            "личное_дело",
        },
        "bmstu_email": {
            "bmstu email",
            "bmstu_email",
            "email",
            "e mail",
            "почта",
            "корпоративная почта",
            "корпоративная_почта",
        },
    },

    "schedule_group_links": {
        "id": {"id", "link id", "id связи"},
        "group_id": {
            "group id",
            "group_id",
            "id группы",
        },
        "schedule_id": {
            "schedule id",
            "schedule_id",
            "id расписания",
        },
    },

    "lessons": {
        "id": {
            "id",
            "lesson id",
            "lesson_id",
            "id занятия",
            "id урока",
        },
        "schedule_id": {
            "schedule id",
            "schedule_id",
            "id расписания",
        },
        "topic": {
            "topic",
            "тема",
            "тема занятия",
            "тема урока",
        },
        "date": {
            "date",
            "дата",
            "дата занятия",
            "дата урока",
        },
    },

    "attendances": {
        "id": {
            "id",
            "attendance id",
            "attendance_id",
            "id посещения",
        },
        "student_id": {
            "student id",
            "student_id",
            "id студента",
        },
        "lesson_id": {
            "lesson id",
            "lesson_id",
            "id занятия",
            "id урока",
        },
        "is_visited": {
            "is_visited",
            "visited",
            "attendance",
            "посещение",
            "посещаемость",
            "присутствовал",
            "был",
        },
    },

    "marks": {
        "id": {
            "id",
            "mark id",
            "mark_id",
            "id оценки",
        },
        "student_id": {
            "student id",
            "student_id",
            "id студента",
        },
        "lesson_id": {
            "lesson id",
            "lesson_id",
            "id занятия",
            "id урока",
        },
        "data": {
            "data",
            "mark",
            "grade",
            "оценка",
            "балл",
            "баллы",
        },
    },

    "comments": {
        "id": {
            "id",
            "comment id",
            "comment_id",
            "id комментария",
        },
        "student_id": {
            "student id",
            "student_id",
            "id студента",
        },
        "lesson_id": {
            "lesson id",
            "lesson_id",
            "id занятия",
            "id урока",
        },
        "data": {
            "data",
            "comment",
            "comments",
            "комментарий",
            "комментарии",
            "замечание",
            "примечание",
        },
    },
}
REFERENCE_FIELD_ALIASES: dict[
    CanonicalEntityType,
    dict[ReferenceKey, dict[str, set[str]]],
] = {
    "students": {
        "group": {
            "name": {
                "group",
                "group name",
                "группа",
                "название группы",
            },
        },
    },

    "schedule_group_links": {
        "group": {
            "name": {
                "group",
                "group name",
                "группа",
                "название группы",
            },
        },
        "schedule": {
            "day": {
                "day",
                "день",
                "день недели",
            },
            "time": {
                "time",
                "время",
                "время занятия",
            },
            "type": {
                "type",
                "тип",
                "тип занятия",
            },
            "odd_or_even": {
                "odd_or_even",
                "odd or even",
                "четность",
                "нечетность",
                "чётность",
            },
        },
    },

    "lessons": {
        "schedule": {
            "day": {
                "day",
                "день",
                "день недели",
            },
            "time": {
                "time",
                "время",
                "время занятия",
            },
            "type": {
                "type",
                "тип",
                "тип занятия",
            },
            "odd_or_even": {
                "odd_or_even",
                "odd or even",
                "четность",
                "нечетность",
                "чётность",
            },
        },
    },

    "attendances": {
        "student": {
            "surname": {
                "surname",
                "фамилия",
                "фамилия студента",
            },
            "first_name": {
                "first name",
                "first_name",
                "имя",
                "имя студента",
            },
            "patronymic": {
                "patronymic",
                "отчество",
                "отчество студента",
            },
        },
        "lesson": {
            "topic": {
                "topic",
                "тема",
                "тема занятия",
                "тема урока",
            },
            "date": {
                "date",
                "дата",
                "дата занятия",
                "дата урока",
            },
        },
    },

    "marks": {
        "student": {
            "surname": {
                "surname",
                "фамилия",
                "фамилия студента",
            },
            "first_name": {
                "first name",
                "first_name",
                "имя",
                "имя студента",
            },
            "patronymic": {
                "patronymic",
                "отчество",
                "отчество студента",
            },
        },
        "lesson": {
            "topic": {
                "topic",
                "тема",
                "тема занятия",
                "тема урока",
            },
            "date": {
                "date",
                "дата",
                "дата занятия",
                "дата урока",
            },
        },
    },

    "comments": {
        "student": {
            "surname": {
                "surname",
                "фамилия",
                "фамилия студента",
            },
            "first_name": {
                "first name",
                "first_name",
                "имя",
                "имя студента",
            },
            "patronymic": {
                "patronymic",
                "отчество",
                "отчество студента",
            },
        },
        "lesson": {
            "topic": {
                "topic",
                "тема",
                "тема занятия",
                "тема урока",
            },
            "date": {
                "date",
                "дата",
                "дата занятия",
                "дата урока",
            },
        },
    },
}


def normalize_tabular_header(header: str) -> str:
    """
    Приводит заголовок колонки к нормализованному виду.

    :param header: Исходный текст заголовка.
    :return: Нормализованный заголовок для сравнения.
    """
    normalized_header = header.strip().lower().replace("ё", "е")
    normalized_header = re.sub(r"[_\-]+", " ", normalized_header)
    normalized_header = re.sub(r"\s+", " ", normalized_header)
    return normalized_header


def build_direct_alias_index() -> dict[CanonicalEntityType, dict[str, str]]:
    """
    Строит индекс прямых алиасов по сущностям.

    :return: Словарь вида `entity_type -> normalized_alias -> field_name`.
    """
    alias_index: dict[CanonicalEntityType, dict[str, str]] = {}

    for entity_type, fields in DIRECT_FIELD_ALIASES.items():
        alias_index[entity_type] = {}
        for field_name, aliases in fields.items():
            for alias in aliases:
                alias_index[entity_type][normalize_tabular_header(alias)] = field_name

    return alias_index


def build_reference_alias_index() -> dict[
    CanonicalEntityType,
    dict[str, tuple[ReferenceKey, str]],
]:
    """
    Строит индекс ссылочных алиасов по сущностям.

    :return: Словарь вида
        `entity_type -> normalized_alias -> (reference_key, field_name)`.
    """
    alias_index: dict[CanonicalEntityType, dict[str, tuple[ReferenceKey, str]]] = {}

    for entity_type, references in REFERENCE_FIELD_ALIASES.items():
        alias_index[entity_type] = {}
        for reference_key, fields in references.items():
            for field_name, aliases in fields.items():
                for alias in aliases:
                    alias_index[entity_type][normalize_tabular_header(alias)] = (
                        reference_key,
                        field_name,
                    )

    return alias_index
