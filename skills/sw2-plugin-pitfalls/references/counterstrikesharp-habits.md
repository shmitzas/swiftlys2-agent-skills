# CounterStrikeSharp habits

Habits from CounterStrikeSharp plugins that compile in SwiftlyS2 and then behave differently. Behaviour differences
only: the official [porting guide][docs-porting] maps the APIs, and SwiftlyS2-Skills' [porting procedure][sws2-porting]
covers how to port feature by feature. Each habit links to the rule that holds the details and the full evidence;
CounterStrikeSharp links point at its tag v312.

## Players

### Don't read `IPlayer.IsValid` as an entity check

**Symptom:** join, chat, menu and disconnect code ported as `if (!player.IsValid) return;` skips players who have no
pawn.

**Cause:** CounterStrikeSharp's `IsValid` checks the entity handle and pointer. SwiftlyS2's `IPlayer.IsValid` also
requires a pawn, although the porting guide maps one to the other.

**Fix:** test the controller in those paths, as [the controller rule][r-controller] describes.

**Evidence:** CounterStrikeSharp [`CEntityInstance.cs` L26][css-isvalid]; porting guide [player
properties][docs-porting-player]. Observed in production, 2026-09.

### Take a player's team from the controller

**Symptom:** players who moved to spectator still count for their old team in rosters and team queries.

**Cause:** CounterStrikeSharp's `CCSPlayerController.Team` reads the controller. SwiftlyS2's team queries and team
targets read the pawn, which keeps its old team until it is destroyed.

**Fix:** read `player.Controller.Team` for rosters, as [the team rule][r-team] describes.

**Evidence:** CounterStrikeSharp [`CCSPlayerController.cs` L14][css-team]. Observed in production, 2026-09.

### Capture identity before the disconnect callback

**Symptom:** cleanup ported from an `OnClientDisconnect(slot)` listener that looks the leaver up by slot finds SteamID
0, or throws `ObjectDisposedException`.

**Cause:** CounterStrikeSharp's `OnClientDisconnect` runs before the engine's disconnect. SwiftlyS2's
`OnClientDisconnected` runs after it, and the `IPlayer` is disposed once the handlers return.

**Fix:** record identity at join or take it from `EventPlayerDisconnect`, as [the leaver rule][r-leaver] describes.

**Evidence:** CounterStrikeSharp [`player_manager.cpp` L75-L76][css-disconnect-hook] and [L236-L250][css-disconnect];
the linked rule for SwiftlyS2. The missed leaver: observed in production, 2026-10. The `ObjectDisposedException`:
inferred from source, not observed.

## Lifecycle and timers

### Expect `OnAllPluginsLoaded` only at server start

**Symptom:** setup that ran in `OnAllPluginsLoaded` is missing after a plugin reload.

**Cause:** CounterStrikeSharp calls `OnAllPluginsLoaded(hotReload: true)` after reloading a plugin. SwiftlyS2 calls it
only once all plugins have loaded at startup.

**Fix:** move work that has to follow every reload to `OnSharedInterfaceInjected`, as [the reload rule][r-reload]
describes.

**Evidence:** CounterStrikeSharp [`PluginContext.cs` L106-L114][css-allloaded]. Inferred from source, not observed.

### Don't read a static `Core` before `Load`

**Symptom:** the plugin fails to load with a `NullReferenceException` thrown from its constructor.

**Cause:** code written against CounterStrikeSharp's static `Server` and `Utilities` classes calls them from
constructors, field initializers and static helpers. Ported to the porting guide's static `Core`, those calls run
before `Load` assigns it.

**Fix:** keep the constructor empty and assign the static first in `Load`, as [the static `Core` rule][r-static-core]
describes.

**Evidence:** porting guide [base structure][docs-porting-base]. The failure: observed in game, 2026-06. Its cause:
inferred from source, not observed.

### Delay the first run of a ported repeating timer

**Symptom:** a timer ported from `AddTimer(interval, ..., TimerFlags.REPEAT)` fires at once on load, paying out a
reward or walking entities during a map load.

**Cause:** CounterStrikeSharp runs a repeating timer for the first time one interval after creating it. SwiftlyS2's
`Repeat` and `RepeatBySeconds` run it on the first scheduler tick.

**Fix:** port it to `DelayAndRepeatBySeconds(interval, interval, ...)`, as [the timer rule][r-timer] describes.

**Evidence:** CounterStrikeSharp [`timer_system.cpp` L204-L213][css-timer]. Observed in production, 2026-07 and
2026-09.

### Keep the config live instead of holding the parsed object

**Symptom:** edits to the config file have no effect until the plugin reloads.

**Cause:** CounterStrikeSharp hands the plugin its parsed config once, in `OnConfigParsed`, and plugins keep that
object. SwiftlyS2 reloads config files while the plugin runs, and a kept object, including the porting guide's
`IOptions<T>.Value`, never changes.

**Fix:** read through `IOptionsMonitor<T>`, as [the monitor rule][r-monitor] describes.

**Evidence:** CounterStrikeSharp [`IPluginConfig.cs` L22-L31][css-config]; porting guide [loading
configuration][docs-porting-config]. Observed in production, 2026-09.

### Queue game calls from classic menu callbacks

**Symptom:** the server crashes or plugin state corrupts when players click options in a `Core.MenusAPI` menu.

**Cause:** CounterStrikeSharp calls a menu option's handler from its `css_1` to `css_9` command handlers. Classic
SwiftlyS2 menus run option callbacks on a thread-pool thread, so a callback written to call game APIs directly races
the game thread.

**Fix:** capture the slot and queue the work with `NextTick`, as [the menu rule][r-menu] describes.

**Evidence:** CounterStrikeSharp [`Application.cs` L94-L103][css-menu-keys] and [`BaseMenu.cs` L133][css-menu-select];
the linked rule for SwiftlyS2. Observed in production, 2026-10.

## Hooks, commands and events

### Return `CancelOriginal` where the old code returned `Handled`

**Symptom:** a ported hook returns `HookResult.Handled`, and the action it should block still happens, while other
plugins' hooks stop seeing it.

**Cause:** in CounterStrikeSharp, `Handled` skips the original and lets other hooks run. In SwiftlyS2, `Handled` skips
the later hooks and lets the original run; `CancelOriginal` has CounterStrikeSharp's meaning.

**Fix:** map `Handled` to `CancelOriginal` and `Stop` to `Stop`, as the official [hook modes and
results][docs-hook-results] table describes.

**Evidence:** CounterStrikeSharp [`HookResult.cs` L18-L26][css-hookresult]. Inferred from source, not observed.

### Filter a client-command hook ported from `AddCommandListener`

**Symptom:** some players can no longer chat or run any command.

**Cause:** CounterStrikeSharp's `AddCommandListener` takes the name of the command to listen to. SwiftlyS2's
`HookClientCommand` handler receives every command a client sends, so a ported body that returns `Stop` blocks all of
them.

**Fix:** return `Continue` first for any other command, as [the client-command rule][r-clientcommand] describes.

**Evidence:** CounterStrikeSharp [`BasePlugin.cs` L211][css-commandlistener]. Observed in production, 2026-07.

### Read `player_hurt` through the `Actual*` members

**Symptom:** ported damage code reads wrong health once a player has more than 255 health.

**Cause:** CounterStrikeSharp's `EventPlayerHurt.Health` and `DmgHealth` are `int`. SwiftlyS2's members of the same
names are obsolete `byte` and `short` casts.

**Fix:** use `ActualHealth`, `ActualDmgHealth` and the other `Actual*` members, as [the `player_hurt`
rule][r-player_hurt] describes.

**Evidence:** CounterStrikeSharp [`GameEvents.g.cs` L4893-L4921][css-playerhurt]. Inferred from source, not observed.

## Entities

### Call `<Field>Updated()` on the changed field, not on its parent struct

**Symptom:** the console floods with `requested resolve all N changes, actually resolved only N-1 changes`.

**Cause:** the porting guide maps `Utilities.SetStateChanged` to the field's generated `<FieldName>Updated()` method.
Calls that named a struct-typed parent, such as `m_AttributeManager`, become the parent's marker, which the engine
cannot resolve.

**Fix:** call the marker of the field you changed, as [the marker rule][r-marker] describes.

**Evidence:** porting guide [modifying schema values][docs-porting-schema]. Observed in production, 2026-09.

### Re-apply transmit blocks that `CheckTransmit` used to apply

**Symptom:** a hidden entity shows up for players who joined after it was hidden.

**Cause:** CounterStrikeSharp's `CheckTransmit` listener lets a plugin edit each client's transmit list whenever it is
built. SwiftlyS2's `SetTransmitState` stores a block once, for the clients connected at that moment.

**Fix:** block restricted entities for each joining client, as [the transmit rule][r-transmit] describes.

**Evidence:** CounterStrikeSharp [`Listeners.g.cs` L171-L172][css-checktransmit]. Observed in game, 2026-09.

[docs-porting]: https://swiftlys2.net/docs/guides/porting-from-css
[docs-porting-base]: https://swiftlys2.net/docs/guides/porting-from-css#base-structure
[docs-porting-player]: https://swiftlys2.net/docs/guides/porting-from-css#player-properties
[docs-porting-config]: https://swiftlys2.net/docs/guides/porting-from-css#loading-configuration
[docs-porting-schema]: https://swiftlys2.net/docs/guides/porting-from-css#modifying-schema-values
[docs-hook-results]: https://swiftlys2.net/docs/development/native-functions-and-hooks#hook-modes-and-results
[sws2-porting]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/porting.md
[css-isvalid]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/Model/CEntityInstance.cs#L26
[css-team]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/Model/CCSPlayerController.cs#L14
[css-allloaded]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/Plugin/PluginContext.cs#L106-L114
[css-timer]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/src/core/timer_system.cpp#L204-L213
[css-config]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/IPluginConfig.cs#L22-L31
[css-hookresult]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/HookResult.cs#L18-L26
[css-commandlistener]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/BasePlugin.cs#L211
[css-playerhurt]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/GameEvents.g.cs#L4893-L4921
[css-checktransmit]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/Listeners.g.cs#L171-L172
[css-disconnect-hook]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/src/core/managers/player_manager.cpp#L75-L76
[css-disconnect]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/src/core/managers/player_manager.cpp#L236-L250
[css-menu-keys]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Core/Application.cs#L94-L103
[css-menu-select]: https://github.com/roflmuffin/CounterStrikeSharp/blob/v312/managed/CounterStrikeSharp.API/Modules/Menu/BaseMenu.cs#L133
[r-controller]: players-and-identity.md#gate-join-chat-menu-and-disconnect-paths-on-the-controller
[r-team]: players-and-identity.md#ask-the-controller-which-team-a-player-is-on
[r-leaver]: players-and-identity.md#read-a-leavers-identity-from-the-disconnect-event
[r-reload]: lifecycle-and-reload.md#dont-rely-on-onallpluginsloaded-after-a-reload
[r-static-core]: lifecycle-and-reload.md#assign-the-static-core-before-anything-reads-it
[r-timer]: threads-and-scheduler.md#use-delayandrepeat-unless-the-first-run-may-happen-now
[r-monitor]: lifecycle-and-reload.md#read-settings-through-the-monitor-not-a-copy
[r-menu]: threads-and-scheduler.md#move-classic-menu-clicks-to-the-game-thread
[r-clientcommand]: commands-and-text.md#filter-a-client-command-hook-to-its-own-command-first
[r-player_hurt]: events-and-hooks.md#read-player_hurt-values-from-the-actual-members
[r-marker]: entities-and-weapons.md#mark-the-field-you-wrote-not-its-parent-struct
[r-transmit]: entities-and-weapons.md#re-apply-transmit-blocks-for-every-joining-client
