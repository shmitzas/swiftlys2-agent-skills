# Audit checklists

Numbered questions for an audit round. Walk [every change](#every-change-x) in every audit, then the section of each
subsystem the change touches; a whole-plugin audit walks them all. Each question can be answered from the diff and its
blast radius, and a "yes" passes. Its link leads to the rule that answers it, with the rule's evidence, mostly in
[`sw2-plugin-pitfalls`](../../sw2-plugin-pitfalls/SKILL.md), so a failed item becomes a finding that cites that rule.

Answer every item you walk: pass, fail, not applicable with the reason, or unchecked with the reason. An item without
an answer counts as unchecked. Cite items by ID, such as `L8` or `T4`, in the report.

| The change touches | Walk |
| --- | --- |
| Anything | [Every change (X)](#every-change-x) |
| `Load`, `Unload`, hot reload, configuration, maps | [Lifecycle and reload (L)](#lifecycle-and-reload-l) |
| Commands, client-command hooks, key binds, permissions, translations, chat and centre text | [Commands, permissions and text (C)](#commands-permissions-and-text-c) |
| Core events, game events, typed game hooks, round flow | [Events and hooks (E)](#events-and-hooks-e) |
| Entities, networked fields, weapons, econ items, sounds | [Entities and weapons (W)](#entities-and-weapons-w) |
| Joins, disconnects, teams, rosters, votes, player input, chat and menu handlers | [Players (P)](#players-p) |
| Timers, `async` code, classic menus, shared caches, per-tick work | [Threads and timers (T)](#threads-and-timers-t) |
| A shared interface, published or consumed, or a contract DLL | [Shared interfaces (S)](#shared-interfaces-s) |
| Player data, databases, migrations | [Persistence (D)](#persistence-d) |
| The project file, packaging or a release | [Packaging and release (R)](#packaging-and-release-r) |
| Code ported from CounterStrikeSharp | [Ported code (H)](#ported-code-h) |
| A HUD, models, menus | [Other skills' checks](#other-skills-checks) |

## Every change (X)

- **X1** Does every hunk serve the request, with no unrequested feature, refactor, rename, reformat or abstraction?
- **X2** Does new code follow the repo's own patterns for naming, layout, logging, config shape and errors
  ([conventions][sws2-csharp])?
- **X3** Is each contract the diff changes approved, and each one it adds listed ([contracts.md](contracts.md))?
- **X4** Does each added comment state what the code cannot express, such as an engine constraint, ownership or the
  reason for a choice, rather than repeat a statement ([comments][sws2-comments])?
- **X5** Does the diff keep the existing comments that are still true?
- **X6** Where behaviour, a setting, a command or a permission changed, are the README, config docs, command tables,
  changelog and version updated the way the repo does them?
- **X7** Is each new or renamed translation key in [every shipped language file][docs-key-design], with the same
  placeholder indices, each meaning the same argument ([`string.Format`][docs-server-localization])?
- **X8** Does every translation file still [parse, with `en.jsonc` among them][ct-translation-files]?
- **X9** Is new player-facing text translated, where the plugin translates its text?
- **X10** Does the diff leave out checks the [producing API already answered][sws2-guarantees]?
- **X11** Does every check the diff removes fall under a case the [guarantees page][sws2-guarantees] lets you remove?
- **X12** Does the diff use what SwiftlyS2 provides, with no wrapper that only renames a framework call and no handling
  for failures nobody has shown ([review custom code][sws2-review])?
- **X13** Where two paths perform one operation, such as a command and a menu, or a command and a shared API, do both
  apply the same permission, limits and confirmation?
- **X14** Where the plugin tells players about failures, do new failure paths do so too, and is every charge paired
  with a [checked write and a refund][pe-done]?
- **X15** Does player-supplied text, such as names, chat and command arguments, reach SQL only as
  [parameters][sws2-database]?
- **X16** Does `Unload` release the managed state that [unloading leaves behind][lr-unload], such as subscriptions to
  other plugins' events, threads and tasks? L15 covers config change subscriptions, and L5
  [game-side cleanup][lr-auto-reload].
- **X17** Does `Unload` leave to SwiftlyS2 what [unloading releases][lr-unload], except where another path also stops
  the same thing ([`Core.Scheduler` guarantee][sws2-guarantees-table], [stop method][sws2-layout-example]), and does
  nothing escape `Unload`?

## Lifecycle and reload (L)

Rules: [lifecycle-and-reload.md](../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md).

- **L1** Does every read of a static `Core` happen [after `Load` assigns it][lr-static-core]?
- **L2** Is [`[SwiftlyInject]`][lr-inject] only on static `ISwiftlyCore` members?
- **L3** Does the plugin use shared interfaces, and report missing ones, only [after the handshake][lr-handshake]?
- **L4** Does work that has to follow every reload run outside [`OnAllPluginsLoaded`][lr-allloaded]?
- **L5** Does `Load` queue its game work for the next tick on a hot reload, and does `Unload` hand its game-side
  cleanup to the game thread [as the automatic-reload rule describes][lr-auto-reload]?
- **L6** Are [`GlobalVars`][lr-globalvars] and the map, player-count and time values read from it used only once a map
  is loaded?
- **L7** Does a map lookup try the [Workshop ID][lr-workshop] before the map name?
- **L8** Are settings read [through the monitor][lr-monitor], never from a copy that nothing refreshes on change?
- **L9** Are hooks, timers and commands chosen from settings in `Load` [chosen again on a change][lr-load-decisions],
  or is the need to reload logged?
- **L10** Are change callbacks free of [writes to the watched file][lr-write-back] and calls to `Reload()`?
- **L11** Does a reload handler that ignores load exceptions refuse [an empty result][lr-atomic]?
- **L12** Is each default collection bound so that [the file's entries replace it][lr-collections]?
- **L13** Does each renamed setting [keep its stored key name][lr-key-name]?
- **L14** Do ignored and computed members have names [no config key uses][lr-ignored]?
- **L15** Are change subscriptions [disposed in `Unload`][lr-dispose]?

## Commands, permissions and text (C)

Rules: [commands-and-text.md](../../sw2-plugin-pitfalls/references/commands-and-text.md).

- **C1** Are engine commands such as `jointeam` [hooked rather than registered][ct-engine]?
- **C2** Does each client-command hook [return `Continue` for other commands][ct-filter] in its first statement?
- **C3** Are key binds read [from key states or the user command, never a client-command hook][ct-binds], and is a
  button that is cleared also cleared in every subtick step?
- **C4** Does each new command and alias have [a name no other plugin uses][ct-names], checked against the other
  plugins the server runs?
- **C5** Does a targeting command [handle a caller with no pawn][ct-target], and refuse ambiguous names for
  destructive actions?
- **C6** Do permission patterns use [`*` and `prefix.*`][ct-perm], with no permission check used as a negative test?
- **C7** Does a translation fallback detect a miss [by its language prefix][ct-missing]?
- **C8** Does player-facing text rely only on the [language codes clients report][ct-custom-lang], with `en.jsonc`
  complete?
- **C9** Do [bracket colours][ct-colours] appear only in chat strings, and HTML only in centre HTML and menus?

## Events and hooks (E)

Rules: [events-and-hooks.md](../../sw2-plugin-pitfalls/references/events-and-hooks.md).

- **E1** Is each handler class other than the plugin [registered once, in `Load`][eh-register]?
- **E2** Does each `[GameHookHandler]` method [take its context by `ref`][eh-ref]?
- **E3** Does each core-event handler [catch its own exceptions][eh-catch]?
- **E4** Does each hook meant to block an action [return `Stop` or `CancelOriginal`][eh-result] from a `Pre` hook?
- **E5** Does the change leave alerts the client builds itself alone, rather than expect [event suppression to hide
  them][eh-suppress]?
- **E6** Does `player_hurt` code read the [`Actual*` members][eh-hurt]?
- **E7** Are buys and pickups refused [in `CanAcquire`][eh-canacquire], with the plugin's own `GiveItem` calls still
  allowed?
- **E8** Does damage code take the attacker from [`AttackerInfo.AttackerPawn`][eh-attacker]?
- **E9** Does each `OnClientKeyStateChanged` handler expect only [the keys it reports][eh-keys], reading other buttons
  in `RunCommand`?
- **E10** Are entities created from connection callbacks [queued for the next tick][eh-connect]?
- **E11** Does match-phase state survive [`round_announce_match_start` firing every round][eh-announce]?
- **E12** Is a pause [re-applied after a cfg's round restart][eh-pause], and `TerminateRound` called only after warmup?
- **E13** Are cvars that never change between phases [kept out of round-transition cfgs][eh-cfg]?

## Entities and weapons (W)

Rules: [entities-and-weapons.md](../../sw2-plugin-pitfalls/references/entities-and-weapons.md).

- **W1** Is each entity kept across ticks held [as a `CHandle`][ew-handle], with unset ones as `CHandle<T>.Invalid`?
- **W2** Are spawned props matched [by index or handle][ew-props], not by designer name?
- **W3** Are transmit blocks [re-applied for each joining client][ew-transmit], and set only through an entity resolved
  this tick, never a stored index?
- **W4** Does each `*Updated()` call [name the field written][ew-marker], not a struct-typed parent?
- **W5** Is each networked field [written only when its value changes][ew-writes]?
- **W6** Does a feature that touches [protected fields][ew-protected] switch itself off cleanly while
  `FollowCS2ServerGuidelines` is on, and does the README say so?
- **W7** Do per-player weapon changes stay out of [shared VData][ew-vdata]?
- **W8** Are `Clip1` writes skipped for [shell-by-shell shotguns][ew-clip1]?
- **W9** Is a weapon [removed by the slot the player holds][ew-remove]?
- **W10** Is the [grenade ammo count cleared][ew-grenade] after a grenade is removed?
- **W11** Is a weapon given back [from its item definition index][ew-defindex]?
- **W12** Does `mp_items_prohibited` [get definition indices][ew-prohibited], and get cleared with `""`?
- **W13** Are custom gloves [cleared through their definition index][ew-gloves]?
- **W14** Is aim punch [reset together with its tick fields][ew-aimpunch]?
- **W15** Is a game-owned `CUtlMap` [walked by index][ew-utlmap]?
- **W16** Are custom sound-event fields [prefixed `public.`][ew-sound]?

## Players (P)

Rules: [players-and-identity.md](../../sw2-plugin-pitfalls/references/players-and-identity.md).

- **P1** Do join, chat, menu and disconnect paths [test the controller][pi-controller], not `IsValid`?
- **P2** Does disconnect cleanup use [identity recorded earlier][pi-leaver], or read from `EventPlayerDisconnect`?
- **P3** Are in-match rosters [keyed by slot or session][pi-rosters], and purged on disconnect?
- **P4** Does per-pawn state [follow a bot takeover][pi-takeover]?
- **P5** Do rosters, capacity checks and votes read [the controller's team][pi-team]?
- **P6** Does each disconnect cleanup step [run in its own `try`][pi-isolate]?
- **P7** Is a vote's quorum [recomputed when a voter leaves][pi-quorum]?
- **P8** Is `PressedButtons` [treated as a sample][pi-buttons], combined with other activity signals?
- **P9** Does a clan-tag change [refresh the scoreboard][pi-clan], and go through one writer?
- **P10** Is [chat from clients not yet in game][pi-chat] refused where it matters?

## Threads and timers (T)

Rules: [threads-and-scheduler.md](../../sw2-plugin-pitfalls/references/threads-and-scheduler.md).

- **T1** Does each repeating timer whose first run has to wait [use `DelayAndRepeat*`][ts-timer]?
- **T2** Are timers [stopped with `Cancel()`][ts-cancel], never disposed?
- **T3** Is validity [checked in the same tick as the native reads it guards][ts-native], log statements included?
- **T4** Does code after an `await`, in `Task.Run`, or in a database or HTTP continuation [use only copied
  values][ts-copy], never a player or entity?
- **T5** Do classic menu clicks [queue their game work for the game thread][ts-menu]?
- **T6** Are the inner collections of a shared cache [concurrent or locked][ts-inner]?
- **T7** Is an action whose effect lands later [latched][ts-latch]?
- **T8** Are network updates [sent on change and throttled per player][ts-tick], not sent to everyone every tick?
- **T9** In per-tick and other hot paths, is each player or entity property [read once][sws2-read-once] per method?

## Shared interfaces (S)

Rules: [dependencies-and-contracts.md](../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md). Changes
to a published interface are also contract changes ([contracts.md](contracts.md)).

- **S1** Does each handshake method [catch its own exceptions][si-throw], and resolve with `TryGetSharedInterface`?
- **S2** Are a soft dependency's contract types named [only in isolated methods][si-soft] that run after a probe?
- **S3** Are a soft dependency's contract structs and enums [kept out of fields, captured locals and `async`
  methods][si-types]?
- **S4** Does the binder [fail closed][si-bind], unsubscribe before it subscribes, and register nothing?
- **S5** Does a breaking contract change [get a new key][si-key], with the old one still served?
- **S6** Does the provider ship [exactly one copy of its contract][si-one-copy], under `resources/exports`, and each
  consumer none?
- **S7** Are generated exports [collected inside a target][si-target]?
- **S8** Does a consumer that builds against another repository's contract [reference a vendored DLL][si-vendor]
  instead of a cross-repo `ProjectReference`?
- **S9** Does the provider [expose state for every event][si-state], and raise the closing event from every exit?
- **S10** Is a change of timing or thread [versioned like a signature change][si-timing]?

## Persistence (D)

Rules: [persistence.md](../../sw2-plugin-pitfalls/references/persistence.md).

- **D1** Is a failed load [treated as unknown][pe-failed], neither cached as empty nor saved over, and retried?
- **D2** Are loaded and saved flags [set only after success][pe-done]?
- **D3** Is earned state [scoped to the server][pe-scope] where servers share a store?
- **D4** Does every per-player collection, static ones included, [drop its entry on disconnect][pe-evict], and every
  TTL cache have a sweep?
- **D5** Is a connection string [taken from an unopened connection][pe-connstr]?
- **D6** Does driver-specific code [switch on the configured driver][pe-driver]?
- **D7** Does each plugin, and each table prefix, get [its own version table][pe-version] on an install whose tables
  don't exist yet, while an install whose tables exist keeps the version table it uses today, with no rows copied?
- **D8** Is each object in a migration [guarded on its own][pe-guard], with a new migration to repair databases that
  ran an old one?
- **D9** Do PostgreSQL branches use [`IfDatabase("PostgreSQL")`][pe-pg]?
- **D10** Are MySQL columns that hold player text [`utf8mb4`][pe-utf8], or are 4-byte characters stripped before
  writing?
- **D11** Does each upsert [have the unique key it relies on][pe-upsert]?
- **D12** Are SQLite primary keys [declared inside `Create.Table`][pe-sqlite]?
- **D13** Does a failed migration [leave a usable database enabled][pe-enabled]?
- **D14** Does database I/O [run off the game thread][sws2-database], with its results applied back on it?

## Packaging and release (R)

Rules: [packaging-and-release.md](../../sw2-plugin-pitfalls/references/packaging-and-release.md).

- **R1** Is `SwiftlyS2.CS2` [pinned to the oldest supported version][pk-version], `MinimumAPIVersion` set to match,
  and every new member present in that version?
- **R2** Is the release [built from a clean output folder][pk-clean]?
- **R3** Is a `GeneratePackageOnBuild` project [built, not packed][pk-pack]?
- **R4** Do the plugin folder, DLL and project names [match in case][pk-case]?
- **R5** Are maps [kept out of content addons][pk-maps] that a plugin mounts?
- **R6** Does the archive hold the plugin folder, its resources and its private dependencies, and [no SwiftlyS2
  assembly][sws2-layout]?

## Ported code (H)

Each row asks: is the port free of this CounterStrikeSharp habit? Search the port as the "Search the port for" column
says; the [habits page](../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md) holds the difference behind
each.

| ID | Ported from | Search the port for | Habit |
| --- | --- | --- | --- |
| H1 | `IsValid` entity checks | `IsValid` in join, chat, menu and disconnect paths | [Validity][cs-isvalid] |
| H2 | `CCSPlayerController.Team` | `GetCT`, `GetT`, `GetInTeam` and team targets in rosters | [Team][cs-team] |
| H3 | Slot lookups in `OnClientDisconnect` | Player lookups and `SteamID` reads in `OnClientDisconnected` | [Identity][cs-identity] |
| H4 | `OnAllPluginsLoaded(hotReload)` | Setup in `OnAllPluginsLoaded` | [Reload][cs-allloaded] |
| H5 | Static `Server` and `Utilities` calls | Static `Core` reads in constructors, initializers and static helpers | [Static `Core`][cs-static] |
| H6 | `AddTimer` with `TimerFlags.REPEAT` | `Repeat` and `RepeatBySeconds` | [Timers][cs-timer] |
| H7 | The config object from `OnConfigParsed` | `IOptions<T>.Value` and settings kept in fields | [Config][cs-config] |
| H8 | Menu callbacks that call game APIs | `Core.MenusAPI` option callbacks | [Menus][cs-menu] |
| H9 | `HookResult.Handled` to block an action | `HookResult.Handled` | [Hook results][cs-handled] |
| H10 | `AddCommandListener` | `HookClientCommand` handlers | [Client commands][cs-listener] |
| H11 | `EventPlayerHurt.Health` and `DmgHealth` | `Health` and `DmgHealth` on `EventPlayerHurt` | [`player_hurt`][cs-hurt] |
| H12 | `Utilities.SetStateChanged` | `Updated()` calls on struct-typed fields | [Markers][cs-marker] |
| H13 | `CheckTransmit` listeners | `SetTransmitState` | [Transmit][cs-transmit] |

## Other skills' checks

- A HUD: the [rules][hud-rules] of `cs2-panorama-hud` and its [delivery checks][hud-delivery].
- Models, precache, and prop or weapon spawns: the [rules][asset-rules] of `sw2-asset-pipeline` and its [delivery
  page][asset-delivery].
- Menus: SwiftlyS2-Skills' [`sws2-menus`][sws2-menus], and its [port checklist][sws2-menu-port] for a menu moved off
  the classic API.

[docs-key-design]: https://swiftlys2.net/docs/development/translations#key-design-best-practices
[docs-server-localization]: https://swiftlys2.net/docs/development/translations#server-side-localization
[sws2-guarantees]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md
[sws2-guarantees-table]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md#guarantees
[sws2-read-once]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md#read-a-property-once
[sws2-review]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/framework-reuse.md#review-custom-code
[sws2-comments]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/csharp.md#types-and-control-flow
[sws2-csharp]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/csharp.md
[sws2-database]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/integration.md#database
[sws2-layout]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/layout.md#template-and-distribution
[sws2-layout-example]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/layout.md#complete-partial-class-example
[sws2-menus]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/SKILL.md
[sws2-menu-port]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/references/migration.md#port-checklist
[hud-rules]: ../../cs2-panorama-hud/SKILL.md#rules
[hud-delivery]: ../../cs2-panorama-hud/references/delivery-checks.md
[asset-rules]: ../../sw2-asset-pipeline/SKILL.md#rules
[asset-delivery]: ../../sw2-asset-pipeline/references/delivery-from-swiftlys2.md
[lr-static-core]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#assign-the-static-core-before-anything-reads-it
[lr-inject]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#put-swiftlyinject-only-on-a-static-iswiftlycore-member
[lr-handshake]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#read-shared-interface-fields-after-the-handshake
[lr-allloaded]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#dont-rely-on-onallpluginsloaded-after-a-reload
[lr-auto-reload]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#keep-game-calls-out-of-load-and-unload-during-an-automatic-reload
[lr-globalvars]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#read-globalvars-once-a-map-is-loaded
[lr-workshop]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#identify-the-running-map-by-its-workshop-id
[lr-monitor]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#read-settings-through-the-monitor-not-a-copy
[lr-load-decisions]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#re-run-decisions-made-in-load-when-the-config-changes
[lr-write-back]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#never-write-the-watched-file-from-a-change-callback
[lr-atomic]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#save-config-files-atomically
[lr-collections]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#know-which-binds-replace-a-default-collection
[lr-key-name]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#keep-the-stored-key-name-when-renaming-a-setting
[lr-ignored]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#dont-let-an-ignored-member-claim-a-config-key-name
[lr-dispose]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#dispose-change-subscriptions-in-unload
[lr-unload]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#release-only-what-unloading-leaves-behind-and-let-unload-return
[ct-engine]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#hook-engine-commands-instead-of-registering-their-names
[ct-filter]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#filter-a-client-command-hook-to-its-own-command-first
[ct-binds]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#read-key-binds-from-the-user-command-not-a-client-command-hook
[ct-names]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#give-each-command-and-alias-a-name-no-other-plugin-uses
[ct-target]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#check-the-callers-pawn-before-findtargettedplayers
[ct-perm]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#grant-everything-with--and-a-subtree-with-prefix
[ct-missing]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#detect-a-missing-translation-by-its-language-prefix
[ct-translation-files]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#ship-enjsonc-and-keep-each-translation-file-parseable
[ct-custom-lang]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#dont-expect-a-custom-language-file-to-reach-players
[ct-colours]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#keep-bracket-colours-to-chat-strings
[eh-register]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#register-handler-classes-other-than-the-plugin-class
[eh-ref]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#take-a-game-hook-context-by-ref
[eh-catch]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#catch-exceptions-inside-each-core-event-handler
[eh-result]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#return-stop-or-canceloriginal-to-block-an-action
[eh-suppress]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#dont-expect-event-suppression-to-hide-game-state-ui
[eh-hurt]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#read-player_hurt-values-from-the-actual-members
[eh-canacquire]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#block-buys-and-pickups-in-canacquire-not-after-item_purchase
[eh-attacker]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#read-the-attacking-pawn-from-attackerinfo
[eh-keys]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#dont-expect-onclientkeystatechanged-to-report-every-key
[eh-connect]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#create-entities-a-tick-after-a-client-connects
[eh-announce]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#expect-round_announce_match_start-every-round-in-some-modes
[eh-pause]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#apply-a-pause-after-the-round-restart-not-next-to-it
[eh-cfg]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#keep-large-cfg-files-out-of-round-transitions
[ew-handle]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#hold-a-chandle-across-ticks-not-the-entity-wrapper
[ew-props]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#track-spawned-props-by-index-not-by-designer-name
[ew-transmit]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#re-apply-transmit-blocks-for-every-joining-client
[ew-marker]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#mark-the-field-you-wrote-not-its-parent-struct
[ew-writes]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#write-networked-fields-when-they-change-not-every-tick
[ew-protected]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#expect-protected-fields-to-throw-while-followcs2serverguidelines-is-on
[ew-vdata]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#treat-weapon-vdata-as-shared-by-every-weapon-of-its-class
[ew-clip1]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#leave-clip1-alone-on-shell-by-shell-shotguns
[ew-remove]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#remove-the-weapon-the-player-holds-not-the-one-you-expect
[ew-grenade]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#clear-the-grenade-ammo-count-after-removing-a-grenade
[ew-defindex]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#re-create-a-weapon-from-its-item-definition-index
[ew-prohibited]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#pass-item-definition-indices-to-mp_items_prohibited
[ew-gloves]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#clear-custom-gloves-through-their-definition-index
[ew-aimpunch]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#reset-aim-punch-together-with-its-tick-fields
[ew-utlmap]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#walk-a-game-owned-cutlmap-by-index
[ew-sound]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#prefix-custom-sound-event-fields-with-public
[pi-controller]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#gate-join-chat-menu-and-disconnect-paths-on-the-controller
[pi-leaver]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#read-a-leavers-identity-from-the-disconnect-event
[pi-rosters]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#key-rosters-by-slot-or-session-and-purge-them-on-disconnect
[pi-takeover]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#follow-the-pawn-through-a-bot-takeover
[pi-team]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#ask-the-controller-which-team-a-player-is-on
[pi-isolate]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#isolate-each-disconnect-cleanup-step
[pi-quorum]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#recompute-a-quorum-when-a-voter-leaves
[pi-buttons]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#treat-pressedbuttons-as-a-sample-not-as-input-since-the-last-check
[pi-clan]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#refresh-the-scoreboard-after-changing-a-clan-tag
[pi-chat]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#expect-chat-from-clients-that-are-not-in-game-yet
[ts-timer]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#use-delayandrepeat-unless-the-first-run-may-happen-now
[ts-cancel]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#cancel-scheduler-timers-instead-of-disposing-them
[ts-native]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#dont-count-on-trycatch-around-native-access
[ts-copy]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#copy-values-before-leaving-the-game-thread
[ts-menu]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#move-classic-menu-clicks-to-the-game-thread
[ts-inner]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#make-the-inner-collection-concurrent-too
[ts-latch]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#latch-an-action-whose-effect-lands-later
[ts-tick]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#dont-send-network-updates-to-every-player-every-tick
[si-throw]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#let-nothing-escape-a-handshake-method
[si-soft]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#keep-a-soft-dependencys-contract-types-out-of-methods-that-always-run
[si-types]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#keep-optional-contract-types-out-of-every-type-in-the-assembly
[si-bind]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#bind-fail-closed-and-register-nothing-in-the-handshake
[si-key]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#add-a-key-for-a-breaking-contract-change
[si-one-copy]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#ship-exactly-one-copy-of-the-contract-in-resourcesexports
[si-target]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#collect-generated-exports-inside-a-target
[si-vendor]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#vendor-the-contract-dll-in-each-consumer-repository
[si-state]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#give-consumers-state-to-read-not-only-events
[si-timing]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#treat-timing-and-thread-changes-as-breaking
[pe-failed]: ../../sw2-plugin-pitfalls/references/persistence.md#treat-a-failed-load-as-unknown-not-as-empty
[pe-done]: ../../sw2-plugin-pitfalls/references/persistence.md#mark-a-load-or-save-done-only-after-it-succeeds
[pe-scope]: ../../sw2-plugin-pitfalls/references/persistence.md#scope-earned-state-to-the-server-when-servers-share-a-store
[pe-evict]: ../../sw2-plugin-pitfalls/references/persistence.md#evict-per-player-caches-on-disconnect-and-sweep-ttl-caches
[pe-connstr]: ../../sw2-plugin-pitfalls/references/persistence.md#take-a-connection-string-from-an-unopened-connection
[pe-driver]: ../../sw2-plugin-pitfalls/references/persistence.md#switch-on-the-configured-driver-not-the-connections-type
[pe-version]: ../../sw2-plugin-pitfalls/references/persistence.md#give-each-plugin-and-each-table-prefix-its-own-version-table
[pe-guard]: ../../sw2-plugin-pitfalls/references/persistence.md#guard-each-object-in-a-multi-object-migration
[pe-pg]: ../../sw2-plugin-pitfalls/references/persistence.md#match-postgresql-with-ifdatabasepostgresql
[pe-utf8]: ../../sw2-plugin-pitfalls/references/persistence.md#store-player-names-in-utf8mb4-columns-on-mysql
[pe-upsert]: ../../sw2-plugin-pitfalls/references/persistence.md#give-an-upsert-the-unique-key-it-relies-on
[pe-sqlite]: ../../sw2-plugin-pitfalls/references/persistence.md#declare-sqlite-primary-keys-inside-createtable
[pe-enabled]: ../../sw2-plugin-pitfalls/references/persistence.md#keep-a-usable-database-enabled-when-a-migration-fails
[pk-version]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#build-against-the-oldest-swiftlys2-you-support-and-declare-it
[pk-clean]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#publish-a-release-from-a-clean-output-folder
[pk-pack]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#build-dont-pack-a-project-with-generatepackageonbuild
[pk-case]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#match-the-case-of-the-plugin-folder-dll-and-project-names
[pk-maps]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#keep-maps-out-of-content-addons-that-a-plugin-mounts
[cs-isvalid]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#dont-read-iplayerisvalid-as-an-entity-check
[cs-team]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#take-a-players-team-from-the-controller
[cs-identity]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#capture-identity-before-the-disconnect-callback
[cs-allloaded]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#expect-onallpluginsloaded-only-at-server-start
[cs-static]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#dont-read-a-static-core-before-load
[cs-timer]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#delay-the-first-run-of-a-ported-repeating-timer
[cs-config]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#keep-the-config-live-instead-of-holding-the-parsed-object
[cs-menu]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#queue-game-calls-from-classic-menu-callbacks
[cs-handled]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#return-canceloriginal-where-the-old-code-returned-handled
[cs-listener]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#filter-a-client-command-hook-ported-from-addcommandlistener
[cs-hurt]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#read-player_hurt-through-the-actual-members
[cs-marker]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#call-fieldupdated-on-the-changed-field-not-on-its-parent-struct
[cs-transmit]: ../../sw2-plugin-pitfalls/references/counterstrikesharp-habits.md#re-apply-transmit-blocks-that-checktransmit-used-to-apply
