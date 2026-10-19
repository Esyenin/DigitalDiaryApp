# Test database

Set `DIGITAL_DIARY_TEST_DATABASE_URL` before running tests that use `db_session`.
The URL must point to a fresh, dedicated database. SQLite filenames and
PostgreSQL database names must begin with `test_`. Test setup refuses any
database that already contains tables and never calls `drop_all()`.

PowerShell example from the repository root:

```powershell
$database = Join-Path (Resolve-Path build) ('test_suite_' + [guid]::NewGuid().ToString('N') + '.db')
$env:DIGITAL_DIARY_TEST_DATABASE_URL = 'sqlite:///' + $database.Replace('\', '/')
.\.venv\Scripts\python.exe -m pytest -q --basetemp=build/pytest-full
```

For PostgreSQL, create a disposable empty database with a `test_` prefix and
set the variable to its SQLAlchemy URL. Never point it at an application
database. The test fixture creates tables but does not remove them afterward.
