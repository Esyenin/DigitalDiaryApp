Схемы данных
============

Пакет ``app.schemas`` содержит Pydantic-схемы, применяемые для нормализации
и проверки данных перед выполнением операций с моделями.

Для предметных сущностей предусмотрены схемы создания, фильтрации,
изменения и удаления.

.. note::

   Содержание раздела формируется из существующих docstring.
   Фактические правила валидации будут проверены отдельно.

Общие схемы и функции валидации
-------------------------------

.. automodule:: app.schemas.base
   :members:
   :show-inheritance:
   :member-order: bysource

Учебная группа
--------------

.. automodule:: app.schemas.group
   :members:
   :show-inheritance:
   :member-order: bysource

Студент
-------

.. automodule:: app.schemas.student
   :members:
   :show-inheritance:
   :member-order: bysource

Расписание
----------

.. automodule:: app.schemas.schedule
   :members:
   :show-inheritance:
   :member-order: bysource

Связь группы с расписанием
--------------------------

.. automodule:: app.schemas.schedule_group_link
   :members:
   :show-inheritance:
   :member-order: bysource

Занятие
-------

.. automodule:: app.schemas.lesson
   :members:
   :show-inheritance:
   :member-order: bysource

Посещаемость
------------

.. automodule:: app.schemas.attendance
   :members:
   :show-inheritance:
   :member-order: bysource

Оценка
------

.. automodule:: app.schemas.mark
   :members:
   :show-inheritance:
   :member-order: bysource

Комментарий
-----------

.. automodule:: app.schemas.comment
   :members:
   :show-inheritance:
   :member-order: bysource
