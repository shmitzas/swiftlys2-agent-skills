# Persistence

Rules for loading and saving player data, per-player caches, connection strings and FluentMigrator schemas. The
[database page][docs-database] covers connections. SwiftlyS2-Skills covers [where database I/O runs][sws2-threads] and
[how its results return to the same connection][sws2-async-results]. The race on inner collections of a shared cache is
in [threads-and-scheduler.md](threads-and-scheduler.md#make-the-inner-collection-concurrent-too).

## Player data

### Treat a failed load as unknown, not as empty

**Symptom:** after a database or web API error at join, a player's saved preferences revert to defaults for the whole
session, and some are overwritten with the defaults in the store.

**Cause:** the failed load cached an empty record so that reads would work, so every key read as absent and nothing
retried. A get-or-default helper then saved the default for each absent key.

**Fix:** track whether a player's data has loaded separately from whether a record is cached. Until it has loaded,
return defaults without caching or saving them, and retry the load on the next read. Merge a completed load with the
writes made while it ran instead of replacing them. Start one load per player: both `OnClientPutInServer` and
`OnClientSteamAuthorize` can start it, so claim it before the first `await` and release the claim in a `finally`.

**Evidence:** plugin logic, no SwiftlyS2 code involved; SwiftlyS2-Skills' [initialization callbacks][sws2-lifetime].
Observed in production, 2026-09.

### Mark a load or save done only after it succeeds

**Symptom:** a load that threw still counts as done, so the retry on the next join signal never runs and the player
keeps defaults.

**Cause:** the plugin set its loaded flag in a `finally`, which also runs when the load throws.

**Fix:** set a loaded flag after the load returns, and a saved baseline after the write commits. Keep a record dirty
while its values differ from the last committed snapshot, so a failed save is sent again with the latest values. Pair
every charge with a checked write and a refund when the write fails.

**Evidence:** plugin logic, no SwiftlyS2 code involved. Observed in production, 2026-09.

### Scope earned state to the server when servers share a store

**Symptom:** an item bought with one server's currency applies on every server.

**Cause:** a player store keyed by SteamID alone is shared by every server that uses the same database or service.

**Fix:** decide per key. Preferences can stay global; earned or purchased state carries a server identity in its key.
Warn at startup when that identity is unset. To move an existing global key to a scoped one, merge the two values, and
never copy one over the other: a failed read looks like an absent key.

**Evidence:** plugin data design, no SwiftlyS2 code involved. Observed in production, 2026-09.

### Evict per-player caches on disconnect, and sweep TTL caches

**Symptom:** per-player caches grow with every player who joined since the last restart, and a player who reconnects
keeps state from the previous session, such as being hidden or invulnerable.

**Cause:** a collection keyed by SteamID has an add path but no removal. A TTL checked only on read never removes an
entry that nobody reads again.

**Fix:** remove each player's entries in the disconnect path, by an identity recorded at join or [read from the
disconnect event](players-and-identity.md#read-a-leavers-identity-from-the-disconnect-event), bots included when a
command can target them. Sweep TTL caches on a timer.

**Evidence:** plugin logic, no SwiftlyS2 code involved, found in a review of plugin code; SwiftlyS2-Skills' [release
points][sws2-lifetime]. Inferred from source, not observed.

## Connections

### Take a connection string from an unopened connection

**Symptom:** FluentMigrator, or another library that takes a connection string, fails with a connection-string format
error, or connects without a password and is denied.

**Cause:** `GetConnectionString` returns the configured URI unchanged when a connection is written as a URI, the format
of the documented example, and drivers expect `key=value` pairs. MySqlConnector removes the password from
`ConnectionString` once a connection has been opened.

**Fix:** let SwiftlyS2 build the connection, and read its string before opening it:

```csharp
string connectionString;
using (var connection = Core.Database.GetConnection(name))
    connectionString = connection.ConnectionString; // before Open()
```

**Evidence:** [`IDatabaseService.cs` L17-L36][src-dbinfo-tostring], [`DatabaseService.cs`
L160-L173][src-dbservice-get], [`DatabaseConnectionManager.cs` L22-L26][src-dbmanager-parse]; [database
configuration][docs-database-config]; MySqlConnector's [connection options][mysqlconnector-options]. The password
removal: reproduced in a test. The URI case: inferred from source, not observed.

### Switch on the configured driver, not the connection's type

**Symptom:** on SQLite the plugin reports an unsupported database, while MySQL and PostgreSQL work.

**Cause:** the plugin matched `Microsoft.Data.Sqlite.SqliteConnection`, and SwiftlyS2 builds SQLite connections with
System.Data.SQLite, a different type.

**Fix:** switch on `Core.Database.GetConnectionInfo(name).Driver`: `mysql`, `postgresql` or `sqlite`.

**Evidence:** [`DatabaseService.cs` L55-L77][src-dbservice-factory]. Reproduced in a test.

## FluentMigrator schemas

### Give each plugin and each table prefix its own version table

**Symptom:** a second server that shares the database with another table prefix never gets its tables, and every query
fails. Tables an operator dropped to reinstall a plugin never come back.

**Cause:** FluentMigrator records applied migrations in one `VersionInfo` table. The second server finds every
migration recorded and runs none, and a reinstall finds its rows still there. Two plugins whose migration numbers
overlap in one database collide the same way.

**Fix:** give an install its own version table: pass `WithVersionTable` an `IVersionTableMetaData` whose table and
unique-index names carry the plugin's name and table prefix. Choose per install, before building the runner, by whether
the install's own tables already exist, for example its first prefixed table. If they don't, as on a new install or
with a prefix whose tables were never created, use the plugin's version table; FluentMigrator creates it empty. If they
do, keep the version table the install uses today: the plugin's own if it exists, otherwise `VersionInfo`.
FluentMigrator applies every migration its version table does not list, so moving such an install to a new, empty
table runs them all again: steps that are not guarded fail and stop the run, and inserts and data updates apply twice.
Don't copy rows from `VersionInfo` into the new table: they don't say which plugin or prefix applied them. To
reinstall, drop the plugin's version table along with its tables.

Keep the version table's names short: PostgreSQL silently truncates identifiers to 63 bytes, which can merge two long
names into one. Prefix index and primary-key names too: PostgreSQL index names are unique per schema and SQLite's per
database, unlike MySQL's, which are per table.

**Evidence:** FluentMigrator v8.0.1 [`DefaultVersionTableMetaData.cs` L46-L61][fm-versiontable],
[`MigrationRunnerBuilderExtensions.cs` L136-L144][fm-withversiontable], [`VersionLoader.cs` L176-L211][fm-loadversion]
and [`MigrationRunner.cs` L531-L568][fm-applyup]; PostgreSQL's [identifiers][pg-identifiers] and
[`CREATE INDEX`][pg-createindex], SQLite's [`CREATE INDEX`][sqlite-createindex]. Separate version tables for three
prefixes in one new database: reproduced in a test. The shared version table skipping a second prefix's migrations,
the re-run when an existing install moves to an empty table, and the other cases: inferred from source, not observed.

### Guard each object in a multi-object migration

**Symptom:** a plugin pointed at an existing database, or restarted after a failed first run, reports
`Table '...' doesn't exist` for one table on every connect, and later migrations never repair it.

**Cause:** one migration created several tables and indexes behind a single "table exists" check. When the first table
already existed, the whole migration returned and was still recorded as applied. MySQL commits each DDL statement on
its own, so a first run that failed after its first `Create.Table` leaves that table without a version row.

**Fix:** check each table and index on its own, and add a new migration that repairs databases which recorded the old
one; share the definitions between the two. Don't guard a MySQL primary key by its name: MySQL names every primary key
`PRIMARY`, so the check is always false.

**Evidence:** MySQL's [implicit commits][mysql-implicit-commit] and [`CREATE TABLE`][mysql-create-table]. Reproduced in
a test.

### Match PostgreSQL with `IfDatabase("PostgreSQL")`

**Symptom:** on PostgreSQL, a step guarded by `IfDatabase("Postgres")` does nothing and the migration is still recorded
as applied. A later statement fails, for example with `42P10` on an `ON CONFLICT` that has no unique index.

**Cause:** `AddPostgres()` registers the PostgreSQL 15 processor, whose names are `PostgreSQL15_0` and `PostgreSQL`,
and `IfDatabase` matches only those names, ignoring case.

**Fix:** use `IfDatabase("PostgreSQL")`. The versioned name moves with FluentMigrator releases.

**Evidence:** FluentMigrator v8.0.1 [`PostgresRunnerBuilderExtensions.cs` L40-L58][fm-addpostgres],
[`Postgres15_0Processor.cs` L51-L54][fm-pg15-names], [`IfDatabaseExpressionRoot.cs` L132-L145][fm-ifdatabase].
Reproduced in a test.

### Store player names in `utf8mb4` columns on MySQL

**Symptom:** saving a player whose name contains an emoji fails with `ERROR 1366 Incorrect string value` on MySQL and
MariaDB.

**Cause:** FluentMigrator maps `AsString` to `NVARCHAR` on MySQL, and MySQL's national character set is the 3-byte
`utf8mb3`. The default strict SQL mode rejects a 4-byte character instead of truncating it.

**Fix:** declare MySQL columns that hold player text as `utf8mb4`, for example with `AsCustom` in an
`IfDatabase("MySql")` branch, or strip 4-byte characters before writing.

**Evidence:** FluentMigrator v8.0.1 [`MySql5TypeMap.cs` L52-L56][fm-mysql-typemap]; MySQL's [national character
set][mysql-national] and [SQL modes][mysql-sql-mode]. Reproduced in a test.

### Give an upsert the unique key it relies on

**Symptom:** on MySQL the table fills with duplicate rows. On PostgreSQL the same upsert fails with
`there is no unique or exclusion constraint matching the ON CONFLICT specification`, and SQLite fails likewise.

**Cause:** `ON DUPLICATE KEY UPDATE` and `ON CONFLICT` act only through a primary key or unique index. A table created
by an older schema, or skipped by a guarded migration, may have none.

**Fix:** create the primary key or unique index in a migration before the first upsert, including on databases that
predate the plugin. Where the table may already hold duplicate rows, remove or merge them in the same migration, then
add the key: adding it over duplicates fails, for example with MySQL error 1062 or PostgreSQL `23505`, and stops
`MigrateUp`.

**Evidence:** MySQL's [`INSERT ... ON DUPLICATE KEY UPDATE`][mysql-on-duplicate] and [server error
reference][mysql-errors]; PostgreSQL's [`ON CONFLICT`][pg-on-conflict] and [`CREATE INDEX`][pg-createindex]. The
upserts: reproduced in a test. The key that fails over duplicate rows: inferred from source, not observed.

### Declare SQLite primary keys inside `Create.Table`

**Symptom:** on SQLite a migration fails with `near "PRIMARY": syntax error` or `SQLite does not support alter column`,
and the migrations after it never run.

**Cause:** `Create.PrimaryKey` emits `ALTER TABLE ... ADD CONSTRAINT ... PRIMARY KEY`, which SQLite does not support,
and the SQLite generator throws on `Alter.Column` in its default strict mode. `MigrateUp` stops at the first failure.

**Fix:** declare primary keys, composite ones included, with `.PrimaryKey()` on the columns in `Create.Table`. On
SQLite, replace a column change with a new table and a copy.

**Evidence:** FluentMigrator v8.0.1 [`SQLiteGenerator.cs` L77][fm-sqlite-strict], [L90-L93][fm-sqlite-altercolumn] and
[L137-L160][fm-sqlite-constraint]; SQLite's [`ALTER TABLE`][sqlite-altertable]. Reproduced in a test.

### Keep a usable database enabled when a migration fails

**Symptom:** on shared hosting, the plugin disables its database features at every start, although its tables exist and
work.

**Cause:** the database user may read and write but not run `CREATE`, `ALTER` or `INDEX`, so a migration fails, and a
catch-all around the migrations turned the plugin off.

**Fix:** run the migrations, keep and log the exception, then probe each table the enabled features need with
`SELECT 1 FROM <table> WHERE 1 = 0`. Disable only when a table is unusable, and name it and the missing privilege;
otherwise warn and continue. Recognise permission errors by MySQL codes 1044, 1142, 1143 and 1227, not 1045, a wrong
password, and by PostgreSQL SQLSTATE `42501`, walking `InnerException`, because FluentMigrator wraps them.

**Evidence:** MySQL's [server error reference][mysql-errors]; PostgreSQL's [error codes][pg-errcodes]. Reproduced in a
test.

[docs-database]: https://swiftlys2.net/docs/development/database
[docs-database-config]: https://swiftlys2.net/docs/development/database#global-database-configuration
[sws2-threads]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-thread-management/references/threads.md
[sws2-lifetime]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/player-state.md#initialize-and-release-state
[sws2-async-results]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/player-state.md#return-asynchronous-results-to-the-same-connection
[src-dbinfo-tostring]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Database/IDatabaseService.cs#L17-L36
[src-dbservice-factory]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Database/DatabaseService.cs#L55-L77
[src-dbservice-get]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Database/DatabaseService.cs#L160-L173
[src-dbmanager-parse]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Database/DatabaseConnectionManager.cs#L22-L26
[fm-versiontable]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.Core/VersionTableInfo/DefaultVersionTableMetaData.cs#L46-L61
[fm-withversiontable]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.Core/MigrationRunnerBuilderExtensions.cs#L136-L144
[fm-loadversion]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.Core/VersionLoader.cs#L176-L211
[fm-applyup]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.Core/MigrationRunner.cs#L531-L568
[fm-addpostgres]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.Postgres/PostgresRunnerBuilderExtensions.cs#L40-L58
[fm-pg15-names]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.Postgres/Processors/Postgres/Postgres15_0Processor.cs#L51-L54
[fm-ifdatabase]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator/Builders/IfDatabase/IfDatabaseExpressionRoot.cs#L132-L145
[fm-mysql-typemap]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.MySql/Generators/MySql/MySql5TypeMap.cs#L52-L56
[fm-sqlite-strict]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.SQLite/Generators/SQLite/SQLiteGenerator.cs#L77
[fm-sqlite-altercolumn]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.SQLite/Generators/SQLite/SQLiteGenerator.cs#L90-L93
[fm-sqlite-constraint]: https://github.com/fluentmigrator/fluentmigrator/blob/v8.0.1/src/FluentMigrator.Runner.SQLite/Generators/SQLite/SQLiteGenerator.cs#L137-L160
[mysqlconnector-options]: https://mysqlconnector.net/connection-options/
[mysql-national]: https://dev.mysql.com/doc/refman/8.4/en/charset-national.html
[mysql-sql-mode]: https://dev.mysql.com/doc/refman/8.4/en/sql-mode.html
[mysql-implicit-commit]: https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html
[mysql-create-table]: https://dev.mysql.com/doc/refman/8.4/en/create-table.html
[mysql-on-duplicate]: https://dev.mysql.com/doc/refman/8.4/en/insert-on-duplicate.html
[mysql-errors]: https://dev.mysql.com/doc/mysql-errors/8.4/en/server-error-reference.html
[pg-identifiers]: https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
[pg-createindex]: https://www.postgresql.org/docs/current/sql-createindex.html
[pg-on-conflict]: https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT
[pg-errcodes]: https://www.postgresql.org/docs/current/errcodes-appendix.html
[sqlite-createindex]: https://www.sqlite.org/lang_createindex.html
[sqlite-altertable]: https://www.sqlite.org/lang_altertable.html
