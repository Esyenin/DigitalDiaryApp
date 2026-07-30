Модели данных
=============

Пакет ``app.models`` содержит SQLAlchemy-модели предметной области.

Все модели наследуются от общего класса ``Base``. Импорт пакета
``app.models`` обеспечивает регистрацию моделей в ``Base.metadata``.

.. note::

   Содержание раздела формируется из существующих docstring.
   Формулировки пока не проходили смысловое редактирование.

Базовая модель
--------------

.. automodule:: app.models.base
   :members:
   :show-inheritance:
   :member-order: bysource

Учебная группа
--------------

.. automodule:: app.models.group
   :members:
   :show-inheritance:
   :member-order: bysource

Студент
-------

.. automodule:: app.models.student
   :members:
   :show-inheritance:
   :member-order: bysource

Расписание
----------

.. automodule:: app.models.schedule
   :members:
   :show-inheritance:
   :member-order: bysource

Связь группы с расписанием
--------------------------

.. automodule:: app.models.schedule_group_link
   :members:
   :show-inheritance:
   :member-order: bysource

Занятие
-------

.. automodule:: app.models.lesson
   :members:
   :show-inheritance:
   :member-order: bysource

Посещаемость
------------

.. automodule:: app.models.attendance
   :members:
   :show-inheritance:
   :member-order: bysource

Оценка
------

.. automodule:: app.models.mark
   :members:
   :show-inheritance:
   :member-order: bysource

Комментарий
-----------

.. automodule:: app.models.comment
   :members:
   :show-inheritance:
   :member-order: bysource
