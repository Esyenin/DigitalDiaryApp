# Проверка документации

Страница определяет последовательность локальных проверок документации
DigitalDiaryApp перед завершением изменения.

Объём проверки зависит от масштаба изменения. Небольшую правку рекомендуется
проверять сразу после внесения, а перед коммитом выполняется строгая сборка
всей документации.

## Быстрая проверка изменённого файла

После изменения отдельной страницы сначала проверяются её структура и
содержимое без полной пересборки документации.

Для просмотра заголовков Markdown-файла используется:

```powershell
Select-String `
    -Path docs/source/<раздел>/<страница>.md `
    -Pattern "^#"
```

Начало и конец конкретного файла проверяются командами:

```powershell
Get-Content `
    docs/source/development/documentation/verification.md `
    -Encoding UTF8 |
    Select-Object -First 30

Get-Content `
    docs/source/development/documentation/verification.md `
    -Encoding UTF8 |
    Select-Object -Last 30
```

Такой просмотр помогает обнаружить случайную перезапись файла, потерянный
заголовок или незакрытый блок.

:::{admonition} Заголовки внутри code block
:class: note

Поиск по шаблону `^#` может находить строки внутри fenced code blocks.
Такой результат сам по себе не означает наличие лишнего раздела.
Итоговая структура дополнительно проверяется после Sphinx-сборки.
:::

## Проверка Git

Перед полной сборкой выполняются:

```powershell
git diff --check
git status --short
```

`git diff --check` не должен сообщать об ошибках пробелов или повреждённых
строк.

Предупреждения Git о будущем преобразовании `CRLF` и `LF` не считаются
ошибкой документации, если `git diff --check` завершается без ошибок.

`git status --short` используется для контроля состава изменения. Перед
коммитом не должны оставаться временные probe-файлы, резервные `*.bak`,
случайные локальные файлы или другие артефакты проверки.

## Проверка структуры и навигации

После создания, удаления или перемещения страницы проверяются:

- наличие страницы в левом sidebar;
- правильное положение в подразделе;
- работа `autotoctree`;
- порядок, заданный через `:order:`;
- переходы на связанные страницы;
- отсутствие неожиданного дублирования навигации.

Для подразделов с автоматической навигацией отдельное ручное изменение
`toctree` обычно не требуется.

## Строгая Sphinx-сборка

Перед завершением изменения выполняется чистая строгая сборка:

```powershell
Remove-Item -Recurse -Force docs/build -ErrorAction SilentlyContinue

& .\.venv\Scripts\python.exe -m sphinx `
    -E `
    -W `
    --keep-going `
    -b html `
    docs/source `
    docs/build/html
```

Ключ `-E` пересоздаёт Sphinx environment. Ключ `-W` преобразует предупреждения
Sphinx в ошибки. `--keep-going` позволяет получить несколько ошибок за один
запуск.

Успешная проверка заканчивается сообщением:

```text
build succeeded.
```

## Проверка автоматического состояния проекта

Расширение `project_status` выполняется при Sphinx-сборке и формирует:

```text
docs/source/_generated/project_status.inc
```

После сборки:

```powershell
Test-Path "docs/source/_generated/project_status.inc"
```

Ожидается `True`.

Для быстрой проверки:

```powershell
Get-Content `
    docs/source/_generated/project_status.inc `
    -Encoding UTF8 |
    Select-Object -First 50
```

Новый файл в известной группе отображается как `NEW FILE`.

Новая неизвестная папка отображается как `NEW DIRECTORY`; файлы внутри неё
отдельно не перечисляются до классификации папки.

Сгенерированный файл не коммитится:

```powershell
git check-ignore `
    -v `
    docs/source/_generated/project_status.inc
```

## Проверка HTML

После успешной сборки проверяется наличие HTML для изменённых страниц:

```powershell
$pages = @(
    "index",
    "organization",
    "structure",
    "writing",
    "statuses",
    "verification",
    "maintenance"
)

foreach ($page in $pages) {
    $path = "docs/build/html/development/documentation/$page.html"
    Write-Host "$page.html -> $(Test-Path $path)"
}
```

Для существующих страниц ожидается `True`.

## Проверка через локальный HTTP-сервер

Поиск и поведение сайта рекомендуется проверять через HTTP.

```powershell
$server = Start-Process `
    -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList `
        "-m", `
        "http.server", `
        "8000", `
        "--directory", `
        "docs/build/html" `
    -PassThru

Write-Host "HTTP server PID: $($server.Id)"
```

После проверки:

```powershell
Stop-Process -Id $server.Id
```

Не следует одновременно запускать несколько серверов на одном порту.

## Проверка поиска

После изменения терминологии, заголовков, структуры или добавления страницы
проверяются название страницы, один предметный термин, один технический
идентификатор, фильтр верхнего раздела и отображение пути.

Примеры:

```text
http://localhost:8000/search.html?q=Student
http://localhost:8000/search.html?q=REQUIRES%20AUDIT
```

## Визуальная проверка

После существенного изменения страницы проверяются:

- левый sidebar;
- правый блок «На этой странице»;
- таблицы;
- code blocks;
- admonition;
- карточки и сетки;
- длинные технические идентификаторы;
- ссылки;
- светлая и тёмная темы, если изменение затрагивает оформление.

Правая панель не должна превращаться в каталог мелких деталей. Если страница
содержит слишком много независимых разделов, предпочтительно разделить её.

## Проверка перед коммитом

Перед коммитом выполняется:

```text
Изменение содержимого
        ↓
Проверка изменённых файлов
        ↓
git diff --check
        ↓
Проверка git status
        ↓
Чистая Sphinx-сборка с -W
        ↓
Проверка автоматической сводки
        ↓
Визуальная проверка
        ↓
Проверка поиска при необходимости
        ↓
Коммит
```

Минимальный набор команд:

```powershell
git diff --check
git status --short

Remove-Item -Recurse -Force docs/build -ErrorAction SilentlyContinue

& .\.venv\Scripts\python.exe -m sphinx `
    -E `
    -W `
    --keep-going `
    -b html `
    docs/source `
    docs/build/html

git diff --check
git status --short
```

Коммит выполняется только после успешной строгой сборки и проверки состава
изменения.
