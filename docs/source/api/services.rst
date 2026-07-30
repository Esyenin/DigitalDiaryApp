Сервисы
*******

Пакет ``app.services`` содержит сервисный слой backend.

Сервисы сущностей связывают SQLAlchemy-модели с соответствующими
Pydantic-схемами. ``OrmService`` предоставляет общий интерфейс выполнения
операций и управляет взаимодействием с SQLAlchemy-сессией.

.. note::

   Содержание раздела формируется из существующих docstring.
   Контракты методов, возвращаемые значения и обработка ошибок будут
   проверены отдельно.

Базовый сервис
--------------

.. automodule:: app.services.base
   :members:
   :show-inheritance:
   :member-order: bysource

ORM-фасад
---------

.. automodule:: app.services.ormservice
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис учебных групп
--------------------

.. automodule:: app.services.group
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис студентов
----------------

.. automodule:: app.services.student
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис расписания
-----------------

.. automodule:: app.services.schedule
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис связей групп и расписания
--------------------------------

.. automodule:: app.services.schedule_group_links
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис занятий
--------------

.. automodule:: app.services.lesson
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис посещаемости
-------------------

.. automodule:: app.services.attendance
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис оценок
-------------

.. automodule:: app.services.mark
   :members:
   :show-inheritance:
   :member-order: bysource

Сервис комментариев
-------------------

.. automodule:: app.services.comment
   :members:
   :show-inheritance:
   :member-order: bysource
