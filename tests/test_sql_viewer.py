"""Adversarial queries against isolated SQLite files only."""

import sqlite3

import pytest

from app.services.sql_viewer import SQLReadOnlyViewer, SQLViewerError


@pytest.fixture
def viewer(tmp_path):
    path = tmp_path / 'test_inspection.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE students(id INTEGER PRIMARY KEY, name TEXT)')
        db.executemany('INSERT INTO students(name) VALUES (?)', [('Ada',), ('Grace',), ('Linus',)])
    return SQLReadOnlyViewer(f'sqlite:///{path}')


@pytest.mark.parametrize('query', [
    'DELETE FROM students', 'UPDATE students SET name="changed"',
    'CREATE TABLE hacked(x)', 'DROP TABLE students',
    "ATTACH DATABASE ':memory:' AS other", 'PRAGMA table_info(students)',
    'PRAGMA query_only=OFF', 'BEGIN', 'COMMIT', 'ROLLBACK',
    'VACUUM', 'SELECT 1; DELETE FROM students',
    "SELECT load_extension('evil')", "SELECT readfile('secret')",
    "SELECT writefile('secret','data')", 'SELECT sqlite_version()',
    'SELECT * FROM pragma_database_list',
    'WITH x AS (SELECT 1) UPDATE students SET name="changed"',
    'WITH x AS (DELETE FROM students RETURNING *) SELECT * FROM x',
    '/* SELECT */ DELETE FROM students',
])
def test_denied_without_mutation(viewer, query):
    before = viewer.execute('SELECT * FROM students')
    with pytest.raises(SQLViewerError):
        viewer.execute(query)
    assert viewer.execute('SELECT * FROM students') == before


def test_select_cte_schema_and_limits(viewer):
    assert viewer.schema() == {'students': ['id', 'name']}
    result = viewer.execute('/* comment */ WITH x AS (SELECT * FROM students) SELECT id, upper(name) FROM x', max_rows=2)
    assert result['rows'] == [(1, 'ADA'), (2, 'GRACE')]
    assert result['truncated']
    assert not viewer.execute('SELECT * FROM students', max_rows=3)['truncated']


def test_timeout_and_recovery(viewer):
    with pytest.raises(SQLViewerError, match='interrupted'):
        viewer.execute('WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT sum(n) FROM x', timeout_ms=1)
    assert viewer.execute('SELECT count(*) FROM students')['rows'] == [(3,)]


def test_schema_and_queries_do_not_change_file(viewer):
    from pathlib import Path
    path = Path(viewer.url.database)
    before = path.read_bytes()
    viewer.schema()
    viewer.execute('SELECT * FROM students')
    assert path.read_bytes() == before


def test_export(viewer, tmp_path):
    path = tmp_path / 'result.txt'
    viewer.save_txt(viewer.execute("SELECT 'Привет' AS name"), path)
    assert path.read_text(encoding='utf-8') == 'name\nПривет\n'


def test_missing_file_not_created(tmp_path):
    path = tmp_path / 'missing.db'
    with pytest.raises(SQLViewerError):
        SQLReadOnlyViewer(f'sqlite:///{path}').schema()
    assert not path.exists()


@pytest.mark.parametrize('query', ['SELECT set_config(\'x\',\'y\',false)',
    'SELECT pg_read_file(\'x\')', 'SELECT public.abs(1)',
    'SELECT 1; SELECT 2', 'WITH x AS (DELETE FROM t) SELECT * FROM x',
    'SELECT "set_config"()', 'SELECT pg_catalog.lo_import(\'x\')'])
def test_postgres_lexical_rejection(query):
    with pytest.raises(SQLViewerError):
        SQLReadOnlyViewer._validate_postgres(query)


def test_postgres_requires_dedicated_url():
    with pytest.raises(SQLViewerError, match='dedicated'):
        SQLReadOnlyViewer('postgresql://unused/test_unused').execute('SELECT 1')


@pytest.mark.parametrize('unsafe_step', [0, 1, 2, 3])
def test_postgres_role_fail_closed(monkeypatch, unsafe_step):
    """Validate connection safety without contacting any PostgreSQL server."""
    import psycopg2

    class Cursor:
        checks = 0

        def execute(self, query, params=None):
            self.query = query

        def fetchone(self):
            unsafe = self.checks == unsafe_step
            self.checks += 1
            return (unsafe,)

    class Connection:
        closed = False

        def rollback(self):
            pass

        def set_session(self, **kwargs):
            assert kwargs == {'readonly': True}

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(psycopg2, 'connect', lambda **kwargs: connection)
    viewer = SQLReadOnlyViewer('postgresql://unused/test_unused',
                               'postgresql://reader@unused/test_unused')
    with pytest.raises(SQLViewerError):
        viewer.execute('SELECT 1')
    assert connection.closed


@pytest.mark.parametrize('query', ["SELECT public.custom_type 'payload'",
    "SELECT date '2026-01-01'", "SELECT E'payload'"])
def test_postgres_typed_literals_denied(query):
    with pytest.raises(SQLViewerError, match='literals'):
        SQLReadOnlyViewer._validate_postgres(query)


@pytest.mark.parametrize('options', [{'max_rows': 0}, {'max_rows': 10001},
    {'timeout_ms': 0}, {'timeout_ms': 10001}, {'max_rows': True}])
def test_bounds(viewer, options):
    with pytest.raises(SQLViewerError):
        viewer.execute('SELECT 1', **options)


@pytest.fixture(scope='module')
def live_postgres_viewer():
    """Opt-in provisioning, exclusively in an explicitly selected empty test DB."""
    import os
    import psycopg2
    from psycopg2 import sql
    from sqlalchemy.engine import make_url

    admin_raw = os.environ.get('DIGITAL_DIARY_SQL_POSTGRES_URL')
    reader_raw = os.environ.get('DIGITAL_DIARY_SQL_READONLY_URL')
    if not admin_raw or not reader_raw:
        pytest.skip('Dedicated SQL viewer PostgreSQL URLs are not configured.')
    admin, reader = make_url(admin_raw), make_url(reader_raw)
    assert admin.get_backend_name() == reader.get_backend_name() == 'postgresql'
    assert admin.database.startswith('test_') and admin.database == reader.database
    assert (admin.host, admin.port) == (reader.host, reader.port)
    assert admin.username != reader.username and not admin.query and not reader.query
    connection = psycopg2.connect(dbname=admin.database, user=admin.username,
        password=admin.password, host=admin.host, port=admin.port, connect_timeout=3)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','f')")
            assert cursor.fetchone()[0] == 0, 'Refusing setup in a nonempty database'
            cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (reader.username,))
            assert cursor.fetchone() is None, 'Refusing to modify an existing role'
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS').format(sql.Identifier(reader.username)))
            cursor.execute('CREATE TABLE public.sql_viewer_sample(id integer PRIMARY KEY, name text)')
            cursor.execute("INSERT INTO public.sql_viewer_sample VALUES (1,'Ada'),(2,'Grace')")
            cursor.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
            cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(reader.username)))
            cursor.execute(sql.SQL('GRANT SELECT ON public.sql_viewer_sample TO {}').format(sql.Identifier(reader.username)))
            # ACL changes are database-local, even for catalog functions.
            cursor.execute("""SELECT p.oid::regprocedure::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE p.provolatile='v' OR n.nspname <> 'pg_catalog'""")
            routines = [row[0] for row in cursor.fetchall()]
            for routine in routines:
                cursor.execute(sql.SQL('REVOKE EXECUTE ON ROUTINE {} FROM PUBLIC').format(sql.SQL(routine)))
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    yield SQLReadOnlyViewer(admin_raw, reader_raw), admin_raw
    # Deliberately retain the database and new role for inspection; no cleanup.


def test_live_postgres_select_schema_and_limit(live_postgres_viewer):
    viewer, _ = live_postgres_viewer
    assert viewer.schema() == {'public.sql_viewer_sample': ['id', 'name']}
    result = viewer.execute('SELECT id, upper(name) FROM public.sql_viewer_sample ORDER BY id', max_rows=1)
    assert result == {'columns': ['id', 'upper'], 'rows': [(1, 'ADA')], 'truncated': True}


@pytest.mark.parametrize('query', ['DELETE FROM public.sql_viewer_sample',
    "UPDATE public.sql_viewer_sample SET name='changed'",
    'WITH x AS (DELETE FROM public.sql_viewer_sample RETURNING *) SELECT * FROM x',
    "SELECT set_config('transaction_read_only','off',false)",
    "SELECT pg_read_file('secret')", "SELECT lo_import('secret')",
    'SELECT 1; SELECT 2', 'COMMIT', 'SET transaction_read_only=off'])
def test_live_postgres_denied(live_postgres_viewer, query):
    viewer, _ = live_postgres_viewer
    with pytest.raises(SQLViewerError):
        viewer.execute(query)
    assert viewer.execute('SELECT count(*) FROM public.sql_viewer_sample')['rows'] == [(2,)]


def test_live_postgres_superuser_denied(live_postgres_viewer):
    _, admin_url = live_postgres_viewer
    with pytest.raises(SQLViewerError, match='administrative'):
        SQLReadOnlyViewer(admin_url, admin_url).execute('SELECT 1')
