"""
Сервис для управления группами.
Наследует все CRUD методы из BaseService.
"""
from typing import Mapping
import re
from app.models.group import MAX_LEN, Group
from app.services.base import BaseService


class GroupService(BaseService[Group]):
    """
    Реализация сервиса.
    Сервис для управления группами.
    """

    DEPARTMENTS = {'ФН', 'Э', 'СМ', 'РЛ', 'ИУ', 'БМТ', 'МТ', 'АК', 'ПС'}

    def __init__(self) -> None:
        """

        """
        super().__init__(Group)

    @staticmethod
    def _correct_type_data(obj: Mapping[str, object]) -> bool:
        """
        Базовая проверка типов данных для модели этого сервиса. Проверяет, что полученные данные соответствуют
        типу данных из колонок базы данных и другим ограничениям на запись.
        :param obj: Словарь с данными, который сверяем с базой данной.
        :return: True, если все данные корректны, False иначе.
        """
        obj_name = obj.get("name")
        obj_speciality = obj.get("speciality")

        # Проверка name
        if obj_name is not None:
            if isinstance(obj_name, str):
                if not 0 < len(obj_name) <= MAX_LEN["name"]:
                    return False
            else:
                return False

        # Проверка speciality
        if obj_speciality is not None:
            if isinstance(obj_speciality, str):
                if not 0 < len(obj_speciality) <= MAX_LEN["speciality"]:
                    return False
            else:
                return False

        return True

    @staticmethod
    def _correct_name(name: str) -> bool:
        """
        Проверка правильности написания названия группы (Примеры: СМ1-21Б, ИУ7-33б БМТ2-11А).
        :param name: Название группы, которое хотим проверить.
        :return: True, если название группы корректно, False иначе.
        """
        # Регулярное выражение для проверки структуры
        pattern = r"^([А-Я]{1,3})([0-9]{1,2})-([0-9]{2})([А-Я]?)$"
        match = re.match(pattern, name)

        if not match:
            return False

        dept, fac_num, group_num, suffix = match.groups()

        # Дополнительная проверка на вхождение в список разрешенных кафедр
        if dept not in GroupService.DEPARTMENTS:
            return False

        return True

    @staticmethod
    def _correct_speciality(speciality: str) -> bool:
        """
        Проверка правильности написания специальности группы (Пример: 11.11.11_специальность).
        :param speciality: Специальность группы, которую хотим проверить.
        :return: True, если специальность группы корректна, False иначе.
        """
        pattern = r"^\d{2}\.\d{2}\.\d{2}_.+$"
        match = re.match(pattern, speciality)

        return bool(match)

    @staticmethod
    def _template_verify(obj: Mapping[str, object]) -> bool:
        """
        Базовая функция проверки для всех verify. Проверяет, что данные соответствуют типу данных колонок в базе данных
        и что записаны в верном формате.
        :param obj: Словарь с данными, которые хотим проверить.
        :return: True, если данные группы корректны, False иначе.
        """
        # Правильный тип данных
        if not GroupService._correct_type_data(obj):
            return False

        # Правильная запись группы
        if isinstance(obj.get("name"), str) and not GroupService._correct_name(obj.get("name")):
            return False

        # Правильная запись специальности
        if isinstance(obj.get("speciality"), str) and not GroupService._correct_speciality(obj.get("speciality")):
            return False

        return True

    def _verify_create(self, obj: Mapping[str, object]) -> bool:
        # Базовая проверка
        if not GroupService._template_verify(obj):
            return False

        # Имя обязательно
        if obj.get("name") is None:
            return False

        return True

    def _verify_get(self, filters: Mapping[str, object]) -> bool:
        return GroupService._template_verify(filters)

    def _verify_update(self, db_obj: Mapping[str, object], upd_obj: Mapping[str, object]) -> bool:
        return GroupService._template_verify(upd_obj)

    def _verify_delete(self, obj: Mapping[str, object]) -> bool:
        return GroupService._template_verify(obj)
