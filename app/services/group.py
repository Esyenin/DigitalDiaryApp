"""
Сервис для управления группами.
Наследует все CRUD методы из BaseService.
"""
from typing import Mapping
import re
from app.models.group import MAX_LEN, Group, Base
from app.services.base import BaseService


class GroupService(BaseService[Group]):
    """
    Реализация сервиса.
    Сервис для управления группами.
    """

    DEPARTMENTS = {'ФН', 'Э', 'СМ', 'РЛ', 'ИУ', 'БМТ', 'МТ', 'АК', 'ПС'}

    def __init__(self) -> None:
        super().__init__(Group)

    @staticmethod
    def _correct_type_data(obj: Mapping[str, object]) -> bool | str:
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
                    return f"Incorrect type data. Incorrect name \"{obj_name}\" length: {len(obj_name)}."
            else:
                return f"Incorrect type data. {obj_name} is {type(obj_name)}."

        # Проверка speciality
        if obj_speciality is not None:
            if isinstance(obj_speciality, str):
                if not 0 < len(obj_speciality) <= MAX_LEN["speciality"]:
                    return (f"Incorrect type data. Incorrect speciality \"{obj_speciality}\""
                            f" length: {len(obj_speciality)}.")
            else:
                return f"Incorrect type data. {obj_speciality} is {type(obj_speciality)}."

        return True

    @staticmethod
    def _correct_name(name: str) -> bool | str:
        """
        Проверка правильности написания названия группы (Примеры: СМ1-21Б, ИУ7-33б БМТ2-11А).
        :param name: Название группы, которое хотим проверить.
        :return: True, если название группы корректно, False иначе.
        """
        # Регулярное выражение для проверки структуры
        pattern = r"^([А-Я]{1,3})([0-9]{1,2})-([0-9]{2})([А-Я]?)$"
        match = re.match(pattern, name)

        if not match:
            return f"Incorrect name. The name looks like {name}."

        dept = match.groups()[0]

        # Дополнительная проверка на вхождение в список разрешенных кафедр
        if dept not in GroupService.DEPARTMENTS:
            return f"Incorrect name. There is no such faculty: {dept} for {name}."

        return True

    @staticmethod
    def _correct_speciality(speciality: str) -> bool | str:
        """
        Проверка правильности написания специальности группы (Пример: 11.11.11_специальность).
        :param speciality: Специальность группы, которую хотим проверить.
        :return: True, если специальность группы корректна, False иначе.
        """
        pattern = r"^\d{2}\.\d{2}\.\d{2}_.+$"
        match = re.match(pattern, speciality)

        if match:
            return True
        return f"Incorrect entry of specialty. Specialty: {speciality}."

    @staticmethod
    def _template_verify(obj: Mapping[str, object]) -> bool:
        """
        Базовая функция проверки для всех verify. Проверяет, что данные соответствуют типу данных колонок в базе данных
        и что записаны в верном формате.
        :param obj: Словарь с данными, которые хотим проверить.
        :return: True, если данные группы корректны, False иначе.
        """
        # Ключи для Groups
        for k in obj.keys():
            if not (k in Base.__dict__.keys() or k in ("name", "speciality")):
                print(f"Incorrect keys. Obj has incorrect key: {k} from {obj} for Group.")
                return False

        # Правильный тип данных
        ctd: bool | str = GroupService._correct_type_data(obj)
        if isinstance(ctd, str):
            print(ctd)
            return False

        # Правильная запись группы
        if isinstance(obj.get("name"), str):
            c_name = GroupService._correct_name(obj.get("name"))
            if isinstance(c_name, str):
                print(c_name)

        # Правильная запись специальности

        if isinstance(obj.get("speciality"), str):
            c_speciality: bool | str = GroupService._correct_speciality(obj.get("speciality"))
            if isinstance(c_speciality, str):
                print(c_speciality)

        return True

    def _verify_create(self, obj: Mapping[str, object]) -> bool:
        # Базовая проверка
        if not GroupService._template_verify(obj):
            return False

        # Имя обязательно
        if obj.get("name") is None:
            print(f"Incorrect type data. The name is None for {obj}.")
            return False

        return True

    def _verify_get(self, filters: Mapping[str, object]) -> bool:
        # Базовая проверка
        if not GroupService._template_verify(filters):
            return False

        # Если есть name, то оно не None
        for k in filters.keys():
            if k == "name" and filters.get(k) is None:
                print(f"Incorrect type data. The name is None for {filters}.")
                return False

        return True

    def _verify_update(self, db_obj: Mapping[str, object], upd_obj: Mapping[str, object]) -> bool:
        # Базовая проверка
        if not GroupService._template_verify(upd_obj):
            return False

        # Если есть name, то оно не None
        for k in upd_obj.keys():
            if k == "name" and upd_obj.get(k) is None:
                print(f"Incorrect type data. The name is None for {upd_obj}.")
                return False

        if len(upd_obj.keys()) == 0:
            print(f"Incorrect type data. Keys not founded for {upd_obj}.")
            return False

        return True

    def _verify_delete(self, obj: Mapping[str, object]) -> bool:
        # Базовая проверка
        if not GroupService._template_verify(obj):
            return False

        # Если есть name, то оно не None
        for k in obj.keys():
            if k == "name" and obj.get(k) is None:
                print(f"Incorrect type data. The name is None for {obj}.")
                return False

        if len(obj.keys()) == 0:
            print(f"Incorrect type data. Keys not founded for {obj}.")
            return False

        return True
