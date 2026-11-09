# Read-only SQL inspection

`SQLWorkspace(window)` embeds in the main window. It uses
`window.repository.engine.url` and optional `window.postgres_readonly_url`.
No ORM session is shared. Results are bounded to 10,000 rows; statements to
10 seconds. TXT is UTF-8 tab-separated text. No commit is performed.
For PostgreSQL, enter the separately provisioned role URL in the masked
connection field and finish editing to refresh. It remains in memory only.

SQLite uses a separate existing-file URI with `mode=ro`, query-only mode,
untrusted schema and an authorizer allowing reads and a small function whitelist.
PRAGMA, transactions, ATTACH, extensions and non-whitelisted functions are denied.
Recursive reads have a monotonic progress deadline. Missing files are not created.

PostgreSQL is opt-in and deliberately restrictive. Configure a separate inspection
role, never an application/owner role. The role must have no administrative or
table-write privileges, no executable non-catalog functions and no executable
volatile catalog functions (including grants inherited through PUBLIC). An
administrator must revoke those grants in the dedicated reporting environment.
The connection uses a read-only transaction, local timeouts and pg_catalog-only
search path. Queries support a conservative plain SELECT subset, not arbitrary
PostgreSQL SQL; schema-qualify application tables. CTEs, quoted identifiers,
custom casts/operators, typed/prefixed literals, comments and unapproved functions are rejected there.
Connection URL options are rejected. The service never weakens role checks.

SQLite tests create temporary files only. PostgreSQL deployment verification
requires an explicitly provisioned dedicated test database and inspection role;
the local tests do not connect to an application PostgreSQL database.

Opt-in live tests use `DIGITAL_DIARY_SQL_POSTGRES_URL` (setup administrator) and
`DIGITAL_DIARY_SQL_READONLY_URL` (new inspection role). Both must target the same
`test_` database. Provisioning refuses nonempty databases and existing roles.
It creates one sample table and a new restricted role, revokes dangerous PUBLIC
function grants only in that database, and retains artifacts for inspection.
Use a fresh database and fresh role for every run. Sessions explicitly roll back
before closing, including errors. These tests were exercised on an isolated
PostgreSQL 18.3 cluster; that does not establish exhaustive SQL grammar safety.

Limits: query execution is synchronous in Qt and can block the UI for the selected
timeout. Row count is bounded, not total byte size of individual cell values.
This is read-only access, not row-level authorization: use a separate reporting
database when the application database contains confidential configuration.
