---
name: sw2-plugin-pitfalls
description: >-
  Rules for SwiftlyS2 plugin bugs that compile cleanly and then misbehave on a Counter-Strike 2 server, each with its
  symptom, cause, fix, evidence and how it was seen. Adds to SwiftlyS2-Skills and the swiftlys2.net docs, which keep
  the authoring basics and the API mapping. Covers lifecycle and hot reload, config reload, commands, permissions and
  translations, events and hooks, entities and weapons, player identity, threads and timers, shared interfaces and
  contract DLLs, persistence and FluentMigrator, packaging, and CounterStrikeSharp habits. Use when a SwiftlyS2 plugin
  crashes the server, a feature silently does nothing, it works on one server but not another, or it breaks after a
  hot reload or a config reload; when a shared interface, a soft dependency or a contract DLL fails to load, or
  MissingMethodException or "Hosting failed to start" appears; when porting from CounterStrikeSharp; and before a
  release.
---

# SwiftlyS2 plugin pitfalls

Rules for the bugs that survive a clean build: a SwiftlyS2 plugin that compiles, loads, and then crashes the server,
does nothing, or behaves differently on another server or after a reload. Each rule comes from an incident or from the
SwiftlyS2 source, and says which.

The basics stay where they are. SwiftlyS2-Skills' [`sws2-authoring`][sws2-authoring] covers plugin structure, the
[framework guarantees][sws2-guarantees] and the porting procedure, and [swiftlys2.net][docs] documents the API. This
skill adds what goes wrong in practice and links those pages instead of repeating them.

Checked against SwiftlyS2 v1.5.2 (2026-11-12) and SwiftlyS2-Skills at commit `b8ce269`. Source links point at the
v1.5.2 tag unless the text names an older one; FluentMigrator rules were checked against FluentMigrator v8.0.1 and the
CounterStrikeSharp habits against CounterStrikeSharp v312.

Look up exact declarations through the SwiftlyS2 MCP or [swiftlys2.net][docs]; the snippets show usage only. If the MCP
is unreachable, download a fresh copy of [`llms-full.txt`][docs-llms-full] and search it rather than reading it whole;
each docs page in it starts at a line beginning `## https://swiftlys2.net/docs`. It has no API reference, so take exact
declarations from the SwiftlyS2 source at the tag of the package version your plugin builds with.

## Pages

| Subsystem | Page | Covers |
| --- | --- | --- |
| Lifecycle | [lifecycle-and-reload.md](references/lifecycle-and-reload.md) | Load order, static `Core`, `[SwiftlyInject]`, hot reload, `OnAllPluginsLoaded`, `GlobalVars`, unloading, Workshop map IDs, config reload |
| Commands and text | [commands-and-text.md](references/commands-and-text.md) | Engine command names, client-command hooks, key binds, aliases, targeting, permission wildcards, translations, colours |
| Events and hooks | [events-and-hooks.md](references/events-and-hooks.md) | Handler registration, hook results, event suppression, `player_hurt`, buy blocking, damage hooks, key states, round flow |
| Entities and weapons | [entities-and-weapons.md](references/entities-and-weapons.md) | Handles, transmit blocks, networked fields, protected fields, weapon VData, ammo, item definition indices, gloves |
| Players | [players-and-identity.md](references/players-and-identity.md) | Validity, identity at disconnect, slots and sessions, bot takeover, teams, quorums, buttons, clan tags |
| Threads and timers | [threads-and-scheduler.md](references/threads-and-scheduler.md) | First timer runs, timer cancellation, native faults, work after `await`, menu click threads, shared caches, tick budget |
| Shared interfaces | [dependencies-and-contracts.md](references/dependencies-and-contracts.md) | The handshake, soft dependencies, versioned keys, the contract DLL and its packaging, contract design |
| Persistence | [persistence.md](references/persistence.md) | Failed loads, save baselines, shared stores, per-player caches, connection strings, FluentMigrator on MySQL, PostgreSQL and SQLite |
| Packaging | [packaging-and-release.md](references/packaging-and-release.md) | The SwiftlyS2 version a plugin builds against, clean publishing, NuGet packing, file-name case, maps in mounted addons |
| Porting | [counterstrikesharp-habits.md](references/counterstrikesharp-habits.md) | CounterStrikeSharp habits that compile in SwiftlyS2 and behave differently |

## Find a rule by symptom

| Symptom or trigger | Rule |
| --- | --- |
| `Hosting failed to start`, and no plugin loads | [Let nothing escape a handshake method][r-handshake-throw], [soft dependencies][r-soft-dep] |
| `Could not load file or assembly '<X>.Contract'` or `Resolving to a collectible assembly is not supported` | [Ship exactly one copy of the contract][r-one-contract] |
| `MissingMethodException: Method not found` when the plugin loads | [Build against the oldest SwiftlyS2 you support][r-min-version] |
| Works on one server and not on another | [Soft dependencies][r-soft-dep], [protected fields][r-guidelines], [file-name case][r-case], [shared stores][r-shared-store] |
| A feature does nothing for players who join after the plugin loaded | [Gate join paths on the controller][r-controller] |
| A handler runs twice, then three times, after reloads | [Bind fail-closed][r-bind], [register handler classes once][r-registrator], [let `Unload` return][r-unload] |
| Replacing the DLL makes `Load` throw `can only be called from the main thread` | [Game calls during an automatic reload][r-auto-reload] |
| Config edits change nothing until the plugin reloads | [Read settings through the monitor][r-monitor], [re-run decisions made in `Load`][r-load-decisions] |
| `CRITICAL: Unobserved task exception` with `The input does not contain any JSON tokens` | [Save config files atomically][r-atomic-save] |
| A blocking hook returns `Handled` and the action still happens | The official [hook modes and results][docs-hook-results] table |
| Some players can no longer chat or run commands | [Filter a client-command hook][r-command-filter] |
| A native crash in code wrapped in `try`/`catch` | [Native faults][r-native-fault], [values copied before `await`][r-copy-values] |
| The server crashes when a player finishes connecting | [Create entities a tick after a client connects][r-connect-tick] |
| Server memory grows with each connected player | [Networked fields written every tick][r-network-writes] |
| `Watchdog timeout exceeded` after `recv queue overflow` | [Network updates every tick][r-tick-budget] |
| A repeating timer fires as soon as the plugin loads | [`DelayAndRepeat*`][r-timer] |
| Saved preferences revert after a database or API error | [Treat a failed load as unknown][r-failed-load] |
| Migrations run, and a plugin's tables never appear | [Version tables][r-version-table], [guard each object][r-guard-migration] |
| Porting from CounterStrikeSharp | [CounterStrikeSharp habits](references/counterstrikesharp-habits.md) |
| Before a release | [Packaging](references/packaging-and-release.md), then the pages for the subsystems the plugin touches |

## How a rule is written

Each rule is a short imperative heading followed by four parts:

- **Symptom**: what an operator or player sees, with exact log lines where there are any.
- **Cause**: why it happens, in the framework, the game or the plugin's own logic.
- **Fix**: what to do instead. A snippet shows usage only; declarations are not copied.
- **Evidence**: SwiftlyS2 source at v1.5.2 or at an older tag the text names, a swiftlys2.net page, or the other source
  the claim rests on, then how the behaviour was seen.

| Level | Meaning |
| --- | --- |
| Observed in production, YYYY-MM | Seen on live servers with real players, or in the release pipeline that ships to them |
| Observed in game, YYYY-MM | Seen in the game on a test or listen server |
| Reproduced in a test | Reproduced outside a game server: against a real database, build or library |
| Inferred from source, not observed | Read from the cited source, or from a plugin's code in a review; nobody has seen it happen |

A rule that combines claims gives each claim its own level. A level is raised only by new evidence of that kind, never
by reasoning.

## Use it

1. Match the symptom in the table above, or open the page for the subsystem the code touches.
2. Check the rule against the SwiftlyS2 version the plugin builds with: open its evidence at that tag, or look the
   members up through the MCP. Rules name the version a behaviour changed in where it did.
3. Apply the fix in the plugin's own style. Treat an "inferred from source" rule as a lead: confirm it on a server
   before relying on it, and report its level with the change.
4. Before a release, read [packaging-and-release.md](references/packaging-and-release.md) and the page of every
   subsystem the change touches.

## What lives elsewhere

| Topic | Go to |
| --- | --- |
| Plugin structure, commands, events, player state, configuration basics | SwiftlyS2-Skills [`sws2-authoring`][sws2-authoring] |
| Porting procedure and API mapping | The official [porting guide][docs-porting] and SwiftlyS2-Skills' [porting page][sws2-porting] |
| Threads, `NextTick`, task ownership | SwiftlyS2-Skills [`sws2-thread-management`][sws2-threads] |
| Menus | SwiftlyS2-Skills [`sws2-menus`][sws2-menus] |
| Profiling | SwiftlyS2-Skills [`sws2-performance-profiler`][sws2-profiler] |
| Models, `SetModel`, precache, prop and weapon spawns, custom knives, Workshop packing | This pack's [`sw2-asset-pipeline`](../sw2-asset-pipeline/SKILL.md) |
| HUD placement and Panorama | This pack's [`cs2-panorama-hud`](../cs2-panorama-hud/SKILL.md) |

[docs]: https://swiftlys2.net
[docs-llms-full]: https://swiftlys2.net/llms-full.txt
[docs-porting]: https://swiftlys2.net/docs/guides/porting-from-css
[docs-hook-results]: https://swiftlys2.net/docs/development/native-functions-and-hooks#hook-modes-and-results
[sws2-authoring]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/SKILL.md
[sws2-guarantees]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md
[sws2-porting]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/porting.md
[sws2-threads]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-thread-management/SKILL.md
[sws2-menus]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/SKILL.md
[sws2-profiler]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-performance-profiler/SKILL.md
[r-handshake-throw]: references/dependencies-and-contracts.md#let-nothing-escape-a-handshake-method
[r-soft-dep]: references/dependencies-and-contracts.md#keep-a-soft-dependencys-contract-types-out-of-methods-that-always-run
[r-one-contract]: references/dependencies-and-contracts.md#ship-exactly-one-copy-of-the-contract-in-resourcesexports
[r-bind]: references/dependencies-and-contracts.md#bind-fail-closed-and-register-nothing-in-the-handshake
[r-min-version]: references/packaging-and-release.md#build-against-the-oldest-swiftlys2-you-support-and-declare-it
[r-case]: references/packaging-and-release.md#match-the-case-of-the-plugin-folder-dll-and-project-names
[r-guidelines]: references/entities-and-weapons.md#expect-protected-fields-to-throw-while-followcs2serverguidelines-is-on
[r-network-writes]: references/entities-and-weapons.md#write-networked-fields-when-they-change-not-every-tick
[r-shared-store]: references/persistence.md#scope-earned-state-to-the-server-when-servers-share-a-store
[r-failed-load]: references/persistence.md#treat-a-failed-load-as-unknown-not-as-empty
[r-version-table]: references/persistence.md#give-each-plugin-and-each-table-prefix-its-own-version-table
[r-guard-migration]: references/persistence.md#guard-each-object-in-a-multi-object-migration
[r-controller]: references/players-and-identity.md#gate-join-chat-menu-and-disconnect-paths-on-the-controller
[r-registrator]: references/events-and-hooks.md#register-handler-classes-other-than-the-plugin-class
[r-connect-tick]: references/events-and-hooks.md#create-entities-a-tick-after-a-client-connects
[r-auto-reload]: references/lifecycle-and-reload.md#keep-game-calls-out-of-load-and-unload-during-an-automatic-reload
[r-unload]: references/lifecycle-and-reload.md#release-only-what-unloading-leaves-behind-and-let-unload-return
[r-monitor]: references/lifecycle-and-reload.md#read-settings-through-the-monitor-not-a-copy
[r-load-decisions]: references/lifecycle-and-reload.md#re-run-decisions-made-in-load-when-the-config-changes
[r-atomic-save]: references/lifecycle-and-reload.md#save-config-files-atomically
[r-command-filter]: references/commands-and-text.md#filter-a-client-command-hook-to-its-own-command-first
[r-native-fault]: references/threads-and-scheduler.md#dont-count-on-trycatch-around-native-access
[r-copy-values]: references/threads-and-scheduler.md#copy-values-before-leaving-the-game-thread
[r-tick-budget]: references/threads-and-scheduler.md#dont-send-network-updates-to-every-player-every-tick
[r-timer]: references/threads-and-scheduler.md#use-delayandrepeat-unless-the-first-run-may-happen-now
