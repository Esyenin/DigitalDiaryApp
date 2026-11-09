# Integrated Teaching Journal

This stage extends the existing Schedule, GroupMembership, LessonParticipant,
academic and teaching architecture. It does not introduce an independent journal.

## Daily Workflow

- The academic workspace opens a period's journal; the teaching workspace opens
  a discipline's journal. Student and group cards link to dated results/history.
- Lesson cards provide explicit roll-call completion, four attendance states,
  attendance corrections, documents, seating and quick behavior actions.
- The embedded journal filters student/group/discipline, period, snapshot date
  and optional inclusive calendar interval. Its tabs show modules/results,
  events/attempts, attendance, behavior, memberships and separate legacy marks.
- A seating workspace creates classrooms, drafts movable seats, saves immutable
  layout revisions, attaches a layout to a lesson and assigns students. Clicking
  an occupied seat exposes attendance, behavior and profile actions.
- PDF reports have curator/dean variants, filters, Qt preview and save.
- SQL inspection has schema navigation, row/time limits, results and UTF-8 TXT
  export. PostgreSQL has a masked read-only-role URL field; it is held in memory,
  not persisted. See SQL_VIEWER.md for role provisioning and restrictions.

## Unified Analytics

`JournalAnalytics` is read-only (`no_autoflush`, no commit or roster fixation).
It reuses `TeachingService.summary` for best/latest attempt policy, defenses,
corrections and module totals. Cards, journal and reports use the same DTOs.

Course totals are earned/maximum, not an average of heterogeneous marks.
Unfulfilled required events with future explicit deadlines are pending, not yet
debts. Missing deadlines retain the established outstanding-event semantics.
Academic points are never changed by a behavior event.

Legacy Mark values remain separate, respect course/date filters and have no
invented event provenance. Past edits of legacy marks cannot be reconstructed.
Group row attendance and group totals use the same historical group scope.
Group/course rosters use dated memberships and recorded participants/results,
not only today's Student.group_id. Former/archived students remain in history.

Present and late are actual visits; excused is a separate absence, not a visit
or unexcused absence. The percentage is (present + late) / all established
participants' lesson opportunities, including excused absences. Unknown rosters
or legacy booleans suppress a precise percentage. No unknown absence is silently
declared an unexcused one. Attendance counters remain visible with warnings.

Excellence requires a comparable maximum of exactly 100, earned 85 through 100,
no debt/pending requirement and complete relevant history. Other scales are
shown explicitly, without unsupported normalization. Averages include sample
counts, exclude unknown results and are suppressed for incomparable scales.

Snapshot dates filter timestamped attempts, corrections, cancellations,
attendance revisions and behavior. `AssessmentEvent.configured_at` is UTC;
unknown old configuration timestamps make past summaries incomplete.
Local calendar dates are converted to UTC instants, including Qt editors.

## Integrity Rules

Seminar-start/end events require a concrete lesson in the same discipline and
module. Service, SQL guards, forms and full archive validation agree.

Future attendance is rejected by the service, old repository path and SQL
INSERT/meaningful UPDATE guards. Attendance changes use TeachingService and
append AttendanceRevision. The old boolean is only a compatible projection.
The revision retains previous status/arrival/lateness, reason, source and UTC
time. Existing unknown audit fields stay NULL rather than being fabricated.

ProofService accepts up to 5 MiB of validated PDF/PNG/JPEG for an excused revision.
It validates safe basenames, dimensions/page bounds, decoded PDF object names
and references (including encoded active actions), SHA-256 and base64 chunks.
No arbitrary client filesystem path is stored or followed. Sealed documents and
their chunks are immutable; read/export validates their content again.

Layout revisions are sealed after their seat coordinates are created. Changes
produce a new revision. LessonLayout preserves the selected template. Seat
assignment history is append-only, with previous_id, reason and operation key.
Database guards plus lesson locks serialize competing assignments, rejecting
two active occupants of one seat or two seats for one student. Transfers do not
rewrite old assignments. Explicit corrections append history.

Behavior has positive/negative categories, student, lesson, comment, source and
UTC time. Canonical quick actions cover knowledge demonstration, participation,
cheating, sleeping, unrelated activity, disruptive talking, safety violations
and an untidy workplace. Custom categories are supported. Correcting a student
appends BehaviorCorrection; the original remains available. No grade penalties.

Closed academic terms retain their existing write guards. Protected schedule
versions and fixed lesson participants are not rewritten by these features.

## Models and Migration

New tables:

| Area | Tables |
| --- | --- |
| Seating | classrooms, seating_layouts, seats, lesson_layouts, seat_assignments |
| Behavior | behavior_categories, behavior_events, behavior_corrections |
| Documents | proof_documents, proof_chunks |

New nullable audit columns on attendance_revisions: previous_status,
previous_arrived_at, previous_late_seconds. New assessment_events.configured_at
is UTC for new events, NULL for unknown historical configuration.

Startup runs prepare_journal_upgrade before metadata changes, snapshotting
existing SQLite files as `.pre-journal-<uuid>.bak`. Activity/proof migrations
also back up when independently adding their tables. Migration operations are
repeatable, additive and retain all pre-existing identifiers/results. No working
database was opened or migrated during development/testing.

SQLite migration writers use explicit transactions. PostgreSQL schema startup
uses a session advisory lock; activity/proof stages use transaction locks.
This prevents competing application instances from racing trigger replacement.
PostgreSQL backups remain an administrator responsibility; startup does not
invoke external dump executables. Multi-stage startup is repeatable, but not a
single transaction across every pre-existing migration module.

The schedule migration also tolerates a partial old schema without lessons.
It does not create invented earliest lesson dates or modify existing IDs.

## Full XLSX Archive

Version 2 includes all academic, membership, schedule, seating, behavior and proof
tables, audit fields and exact finite seat coordinates. Validation precedes
writes: context, references, correction/assignment chains, sealed state,
participants, hashes and document payloads. Restore stages unsealed layouts and
documents, fills children, seals, reinstalls guards and commits atomically.

The exact old v1 manifest is supported. New tables are empty and missing audit/
configuration fields remain unknown. Altered manifests and unsafe graphs are
rejected, not repaired heuristically. Restore is into an empty database only;
this is not a merge operation. Smart Import recognition was not rewritten.

## Verification

Tests use only new named SQLite files and explicitly allocated empty PostgreSQL
databases. Fixtures refuse nonempty databases; no drop_all on application data.
QT_QPA_PLATFORM=offscreen is used for UI integration. Choose fresh paths and
fresh test_ databases/roles for every run.

```powershell
$env:DIGITAL_DIARY_TEST_DATABASE_URL='sqlite:///build/test_journal_fresh.db'
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q -rs --basetemp=build/journal_fresh
```

Optional PostgreSQL variables are documented in README and SQL_VIEWER.md. The
education/membership/schedule/journal source/restore databases must be different
and empty. SQL tests require an additional empty test_ database and a new role;
they revoke unsafe PUBLIC function grants only inside that disposable database.
Never provision this test role against a production database.

The real Qt acceptance test covers period -> discipline -> lesson -> roll call
-> layout/seat -> late arrival -> behavior -> test -> laboratory defense ->
consultation/resit -> updated student profile -> Cyrillic PDF -> read-only SQL.
It then transfers/archives the student and verifies old IDs/results/seating.

PDF tests cover actual Cyrillic text, multiple pages, repeated headings, 80
students, long names and a single student with 60 courses; rendered pages and
Qt previews were inspected. SQL tests cover writes, DDL, multi-statements,
configuration/functions, timeout, bounds, export and a live restricted PG role.

Verification on 2026-11-09:

- Full SQLite run before the final added migration regression: 1809 passed,
  0 failed, 19 skipped (18 optional live-PG checks and one absent local XLSX).
- Full generic fixture run on PostgreSQL 18.3 before the last three small
  regressions: 1805 passed, 0 failed, 19 skipped. Tests with private SQLite
  fixtures still used SQLite; this is not a claim that every test runs on PG.
- Final full run with all live PostgreSQL integrations: 1828 passed, 0 failed,
  1 skipped, 56.36 seconds. The only skip is the absent local XLSX below.
- Live PG coverage comprises 18 tests: academic guards/concurrency (4),
  memberships (1), schedule migration/versioning (1), full journal/archive/
  concurrent seats (1), SQL viewer restricted role and denied queries (11).
- Both real Qt acceptance scenarios passed. The old-schema SQLite migration
  regression verifies backup contents, all old rows/IDs and repeated startup.
- compileall and git diff --check completed without errors.

The temporary PostgreSQL cluster listens only on loopback in a workspace build
directory. It is separate from the application database and is stopped after
testing. Test artifacts are not included in the commit. The missing XLSX is
`logs/test_io_tools_smart_reader.xlsx`; generated archive/Smart Import tests
remain covered, but that external fixture was not fabricated for a green run.

## Known Limits

- Dates of old transfers and full old lesson rosters cannot be reconstructed.
  Evidence of one student's participation does not prove the whole roster.
- Membership has day precision. Multiple transfers within a day cannot recover
  intra-day ordering relative to lesson times. This stage adds no false times.
- Snapshot analytics is not a full temporal database: current student status,
  current labels and mutable old descriptive metadata remain current. Historical
  group_on_date is separate; old configuration without timestamps is flagged.
- Unknown previous attendance fields are retained as unknown. No old seating
  or behavior is inferred. Legacy marks are not converted into academic points.
- PDF validation reduces active-content risk, but is not malware scanning or a
  sandbox. Size/page/object limits are conservative and may reject complex PDFs.
- SQL is a restricted read-only inspection tool, not full SQL compatibility or
  row-level authorization. PostgreSQL requires hardened role ACLs; its accepted
  grammar is deliberately narrow. Query execution is synchronous and can block
  Qt until the timeout; individual cell byte lengths are not bounded.

## Changed Files

Models: app/models/__init__.py, education.py, journal_activity.py,
attendance_proof.py.

Services: app/services/teaching.py, journal_analytics.py, journal_activity.py,
journal_reports.py, attendance_proof.py, sql_viewer.py.

Data: app/ui/data/repository.py, academic_migration.py, schedule_migration.py,
activity_migration.py, proof_migration.py, journal_migration.py, teaching_archive.py.

UI: app/ui/widgets/group_card.py; app/ui/windows/ui_MainWindowsUI.py,
academic_workspace.py, teaching_workspace.py, journal_workspace.py,
seating_workspace.py, proof_dialog.py, reports_workspace.py, sql_workspace.py.

Tests: tests/test_academic_structure.py, test_attendance_proof.py,
test_journal_activity.py, test_seating_ui.py, test_journal_analytics.py,
test_journal_acceptance.py, test_journal_archive.py, test_journal_postgresql.py,
test_journal_reports.py, test_reports_ui.py, test_sql_viewer.py,
test_sql_viewer_ui.py.

Documentation/dependencies: README.md (journal section only),
JOURNAL_INTEGRATION.md, SQL_VIEWER.md, requirements.txt.
