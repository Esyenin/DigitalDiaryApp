# DigitalDiaryApp

**Локальный электронный дневник преподавателя**

:::{admonition} Статус документации
:class: note

Документация является архитектурным снимком проекта.

- Ветка: `docs/project-baseline`
- Коммит baseline: `c31d21ed28219fbcbc07a63861f727571ecd0047`
- Python: `3.14.0`
- Backend-тесты: `1438 passed`
- Pylint для `models`, `schemas`, `services`: `9.94/10`
:::

DigitalDiaryApp — студенческий проект электронного дневника, рассчитанный
на реальное использование преподавателями.

Документация предназначена для:

- разработчиков проекта;
- преподавателей;
- будущих участников разработки;
- Codex и других ИИ-агентов.

::::{grid} 1 2 3 3
:gutter: 3

:::{grid-item-card} О проекте
:link: project/index
:link-type: doc

Назначение, пользователи, готовый функционал и ограничения.
:::

:::{grid-item-card} Архитектура
:link: architecture/index
:link-type: doc

Устройство backend и взаимодействие слоёв.
:::

:::{grid-item-card} Разработка
:link: development/index
:link-type: doc

Запуск, проверки и правила расширения проекта.
:::

:::{grid-item-card} Состояние
:link: status/index
:link-type: doc

Текущая готовность, метрики и известные проблемы.
:::

:::{grid-item-card} API
:link: api/index
:link-type: doc

Модели, схемы и сервисы.
:::

:::{grid-item-card} Для ИИ
:link: ai/index
:link-type: doc

Структурированный контекст и правила работы с проектом.
:::

::::

:::{toctree}
:hidden:
:maxdepth: 3

project/index
architecture/index
development/index
status/index
api/index
ai/index
:::