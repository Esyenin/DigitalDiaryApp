"""Independent, fail-closed SQL inspection connections; never uses ORM sessions."""

import csv
import io
import re
import sqlite3
from pathlib import Path
from time import monotonic

from sqlalchemy.engine import make_url


class SQLViewerError(ValueError):
    """A rejected query or unavailable read-only connection."""


SAFE_FUNCTIONS = frozenset('abs avg coalesce count hex ifnull instr length like lower ltrim max min nullif quote replace round rtrim substr substring sum total trim typeof upper'.split())


class SQLReadOnlyViewer:
    def __init__(self, database_url, postgres_readonly_url=None):
        self.url = make_url(database_url)
        self.postgres_url = postgres_readonly_url

    @staticmethod
    def _close(connection):
        try:
            connection.rollback()
        finally:
            connection.close()

    def _sqlite(self):
        if not self.url.database or self.url.database == ':memory:' or self.url.query:
            raise SQLViewerError('A plain existing SQLite file is required.')
        uri = Path(self.url.database).resolve().as_uri() + '?mode=ro'
        connection = sqlite3.connect(uri, uri=True, timeout=0.1)
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.enable_load_extension(False)
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE}

        def authorize(action, arg1, arg2, database, source):
            if action == sqlite3.SQLITE_FUNCTION:
                return sqlite3.SQLITE_OK if (arg2 or '').lower() in SAFE_FUNCTIONS else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        return connection

    def _postgres(self, timeout_ms):
        if not self.postgres_url:
            raise SQLViewerError('Configure a dedicated PostgreSQL read-only role URL.')
        import psycopg2
        url = make_url(self.postgres_url)
        if url.get_backend_name() != 'postgresql' or url.query:
            raise SQLViewerError('PostgreSQL connection overrides are not allowed.')
        connection = psycopg2.connect(dbname=url.database, user=url.username,
            password=url.password, host=url.host, port=url.port, connect_timeout=3)
        try:
            connection.set_session(readonly=True)
            cursor = connection.cursor()
            cursor.execute("SET LOCAL search_path = pg_catalog")
            cursor.execute('SET LOCAL statement_timeout = %s', (timeout_ms,))
            cursor.execute('SET LOCAL lock_timeout = %s', (min(timeout_ms, 500),))
            cursor.execute('''SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
                FROM pg_roles WHERE rolname=current_user''')
            if cursor.fetchone()[0]:
                raise SQLViewerError('The inspection role has administrative privileges.')
            cursor.execute('''SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND c.relkind IN ('r','p','v','f')
                AND (has_table_privilege(c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')
                     OR has_any_column_privilege(c.oid, 'INSERT,UPDATE,REFERENCES')))''')
            if cursor.fetchone()[0]:
                raise SQLViewerError('The inspection role has write privileges.')
            cursor.execute('''SELECT EXISTS (SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                AND c.relkind IN ('v','m','f') AND has_table_privilege(c.oid,'SELECT'))
                OR EXISTS (SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
                JOIN pg_type t ON t.oid=a.atttypid JOIN pg_namespace n ON n.oid=t.typnamespace
                JOIN pg_namespace cn ON cn.oid=c.relnamespace
                WHERE a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','p')
                AND cn.nspname NOT IN ('pg_catalog','information_schema')
                AND n.nspname <> 'pg_catalog' AND has_table_privilege(c.oid,'SELECT'))''')
            if cursor.fetchone()[0]:
                raise SQLViewerError('Inspection requires plain tables with built-in column types, not views or foreign tables.')
            # PUBLIC execution grants must also be revoked by the administrator.
            cursor.execute('''SELECT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE has_function_privilege(p.oid,'EXECUTE')
                AND (n.nspname <> 'pg_catalog' OR p.provolatile='v'))''')
            if cursor.fetchone()[0]:
                raise SQLViewerError('Role can execute unsafe functions; revoke PUBLIC and role grants first.')
            cursor.close()
            return connection
        except BaseException:
            self._close(connection)
            raise

    @staticmethod
    def _validate_postgres(query):
        # Deliberately small lexical subset, not a general PostgreSQL parser.
        # Quoted identifiers, comments and dollar strings cannot hide commands.
        if re.search(r'--|/\*|;|\$|"|\\', query):
            raise SQLViewerError('Unsupported SQL syntax in PostgreSQL inspection query.')
        for literal in re.finditer(r"'(?:''|[^'])*'", query):
            previous = re.search(r'([\w.]+)\s*$', query[:literal.start()])
            if previous and previous.group(1).lower() not in {'select', 'then', 'else', 'like', 'ilike'}:
                raise SQLViewerError('Typed and prefixed literals are not supported.')
        stripped = re.sub(r"'(?:''|[^'])*'", "''", query)
        if "'" in stripped.replace("''", ''):
            raise SQLViewerError('Unterminated SQL literal.')
        words = re.findall(r'[A-Za-z_][A-Za-z_0-9]*', stripped.lower())
        forbidden = set('insert update delete merge create drop alter truncate grant revoke copy call do set reset show begin commit rollback into lock vacuum analyze explain execute prepare values with recursive'.split())
        if not words or words[0] != 'select' or forbidden.intersection(words):
            raise SQLViewerError('Only plain read-only SELECT queries are supported on PostgreSQL.')
        for match in re.finditer(r'([\w.]+)\s*\(', stripped.lower()):
            if match.group(1) not in SAFE_FUNCTIONS | {'in'}:
                raise SQLViewerError('Function or SQL construct is not allowed.')
        if re.search(r'::|\[|\]|@|#|~|!|\|', stripped):
            raise SQLViewerError('Custom casts and operators are not supported.')

    def schema(self):
        connection = None
        try:
            if self.url.get_backend_name() == 'sqlite':
                connection = self._sqlite()
                tables = connection.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                result = {}
                for (table,) in tables:
                    quoted = '"' + table.replace('"', '""') + '"'
                    result[table] = [column[0] for column in connection.execute(f'SELECT * FROM {quoted} LIMIT 0').description]
                return result
            if self.url.get_backend_name() != 'postgresql':
                raise SQLViewerError('Unsupported database backend.')
            connection = self._postgres(2000)
            cursor = connection.cursor()
            cursor.execute("SELECT table_schema,table_name,column_name FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_schema,table_name,ordinal_position")
            result = {}
            for schema, table, column in cursor:
                result.setdefault(f'{schema}.{table}', []).append(column)
            return result
        except Exception as exc:
            raise SQLViewerError('Cannot inspect read-only schema: ' + str(exc)) from exc
        finally:
            if connection is not None:
                self._close(connection)

    def execute(self, query, max_rows=500, timeout_ms=2000):
        if not isinstance(query, str) or not query.strip() or len(query) > 100000:
            raise SQLViewerError('Provide a query of at most 100000 characters.')
        if type(max_rows) is not int or not 1 <= max_rows <= 10000:
            raise SQLViewerError('Row limit must be between 1 and 10000.')
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 10000:
            raise SQLViewerError('Timeout must be between 1 and 10000 ms.')
        connection = None
        try:
            if self.url.get_backend_name() == 'sqlite':
                connection = self._sqlite()
                deadline = monotonic() + timeout_ms / 1000
                connection.set_progress_handler(lambda: int(monotonic() >= deadline), 100)
                cursor = connection.execute(query)
            elif self.url.get_backend_name() == 'postgresql':
                self._validate_postgres(query)
                connection = self._postgres(timeout_ms)
                cursor = connection.cursor(name='diary_inspection')
                cursor.execute(query)
                # Named cursors acquire description on their first fetch.
            else:
                raise SQLViewerError('Unsupported database backend.')
            rows = cursor.fetchmany(max_rows + 1)
            if cursor.description is None:
                raise SQLViewerError('A result-producing query is required.')
            return dict(columns=[item[0] for item in cursor.description],
                        rows=[tuple(row) for row in rows[:max_rows]], truncated=len(rows) > max_rows)
        except Exception as exc:
            raise SQLViewerError('Read-only query rejected: ' + str(exc)) from exc
        finally:
            if connection is not None:
                self._close(connection)

    @staticmethod
    def save_txt(result, path):
        buffer = io.StringIO(newline='')
        writer = csv.writer(buffer, delimiter='\t', lineterminator='\n')
        writer.writerow(result['columns'])
        writer.writerows(result['rows'])
        if result['truncated']:
            writer.writerow(['[Result truncated]'])
        Path(path).write_text(buffer.getvalue(), encoding='utf-8')
