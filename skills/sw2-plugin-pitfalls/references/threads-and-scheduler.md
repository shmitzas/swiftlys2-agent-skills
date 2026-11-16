# Threads and the scheduler

Rules for timers, native access and work that crosses threads. SwiftlyS2-Skills' [dispatch and lifetime][sws2-threads]
covers `async` handlers, `NextTick` and `NextTickAsync`, `*Async` members and task ownership, and the official [thread
safety][docs-thread-safety] page lists the thread-unsafe APIs. Game calls made during an automatic hot reload are in
[lifecycle-and-reload.md](lifecycle-and-reload.md#keep-game-calls-out-of-load-and-unload-during-an-automatic-reload).

## Timers

### Use `DelayAndRepeat*` unless the first run may happen now

**Symptom:** a repeating timer pays out a reward on every plugin load or restart, or crashes the server when its first
run walks players or entities during a map load.

**Cause:** `Repeat` and `RepeatBySeconds` run the callback on the first scheduler tick, then every period. Only
`DelayAndRepeat` and `DelayAndRepeatBySeconds` wait first.

**Fix:** use `DelayAndRepeatBySeconds(period, period, ...)` by default. Keep `RepeatBySeconds` for callbacks that may
run at once and touch no entities.

**Evidence:** [`SchedulerService.cs` L123-L136 and L170-L190][src-sched-repeat]; [tick-based timers][docs-sched-ticks].
The crash: observed in production, 2026-07. The repeated payout: observed in production, 2026-09.

### Cancel scheduler timers instead of disposing them

**Symptom:** after a map change, timers passed to `StopOnMapChange` stop the moment they are created, for one map, and
the plugin's own `OnMapUnload` handlers skip that map change.

**Cause:** `StopOnMapChange` registers the timer's `Cancel` on the scheduler's map-change token. If the plugin disposed
that timer, cancelling the token on map unload makes the callback throw, and the token reports it as an
`AggregateException`. The scheduler only catches `ObjectDisposedException`, so its handler stops before it replaces the
cancelled token, and the exception ends the plugin's other `OnMapUnload` handlers. Until the next unload, every
registration on the cancelled token runs at once.

**Fix:** stop timers with `Cancel()` only. The scheduler drops cancelled timers and cancels the rest when the plugin
unloads.

**Evidence:** [`SchedulerService.cs` L15-L30][src-sched-mapchange] and [L197-L200][src-sched-stoponmap],
[`EventSubscriber.cs` L466-L472][src-subscriber-mapunload]; Microsoft's
[`CancellationTokenSource.Cancel`][ms-cts-cancel]. Inferred from source, not observed.

## Native access

### Don't count on `try`/`catch` around native access

**Symptom:** the server dies with a native fault in code wrapped in `try`/`catch`. The managed trace can end in
`SpanHelpers.IndexOfNullByte` under `CBasePlayerControllerImpl.get_PlayerName`.

**Cause:** reading through a dangling or null native pointer is an access violation, and .NET does not deliver that to
a `catch` block. `IPlayer.Controller` is never null, an empty slot gives a wrapper at address 0, so `?.` guards
nothing.

**Fix:** check validity in the same tick, right before the read: `player.Controller is { IsValid: true }`, a non-null
`handle.Value`. Keep reads of names and pawns below those checks, including in log statements.

**Evidence:** [`Player.cs` L58][src-player-controller]; Microsoft's
[`HandleProcessCorruptedStateExceptionsAttribute`][ms-corrupted-state]. Observed in production, 2026-07.

### Copy values before leaving the game thread

**Symptom:** the server crashes when a web API or database is slow. The faulting thread is a thread-pool thread running
a continuation that reads `IPlayer` or walks the player list.

**Cause:** code after an `await` runs on a thread-pool thread, where player and entity reads race the game thread. A
stalled API stretches the window from milliseconds to seconds, so a race that never fired starts crashing.

**Fix:** copy SteamIDs, slots and session IDs before the call and resolve the player again on the game thread, as
SwiftlyS2-Skills' [dispatch and lifetime][sws2-threads] shows.

**Evidence:** [thread safety][docs-thread-safety]. Observed in production, 2026-09.

### Move classic menu clicks to the game thread

**Symptom:** the server crashes, or plugin state corrupts, when players click buttons in a `Core.MenusAPI` menu.

**Cause:** the classic menu runs every option click inside `Task.Run`, in both input modes, so the click handler runs
on a thread-pool thread. `Core.Menu` runs handlers on the game thread up to their first real `await`.

**Fix:** in a classic menu click, capture the slot, queue the work with `Core.Scheduler.NextTick` and resolve the
player again there. New menus belong on `Core.Menu`, covered by SwiftlyS2-Skills' [`sws2-menus`][sws2-menus].

**Evidence:** [`MenuManagerAPI.cs` L229-L233][src-menus-click] and [L378-L382][src-menus-click-wasd]; SwiftlyS2-Skills
[legacy built-in menus][sws2-menus-legacy]. Observed in production, 2026-10.

## Shared state

### Make the inner collection concurrent too

**Symptom:** a cache throws `Operations that change non-concurrent collections must have exclusive access`, loses
entries, or reads back defaults.

**Cause:** a `ConcurrentDictionary` whose values are plain `Dictionary` or `List` objects protects only the outer map.
Async loads that resume on thread-pool threads write the same inner collection at once.

**Fix:** make the inner collections concurrent, or lock each one, and replace `Remove(key)` with
`TryRemove(key, out _)`.

**Evidence:** .NET behaviour, no SwiftlyS2 code involved. Observed in production, 2026-09.

### Latch an action whose effect lands later

**Symptom:** one menu choice takes effect twice: two announcements, a side switch applied and undone.

**Cause:** the action defers its state change by a tick or a delay. Until it lands, every path's state check still
passes, and the menu stays clickable because something else closes it later.

**Fix:** set a one-shot latch in the one method every path reaches, and reset it only when the phase starts again. On
the menu side, release a claim when the menu opens, when the action fails, or on teardown, never on a close the action
itself triggers, and give it a timeout for actions that get rejected silently.

**Evidence:** plugin logic, no SwiftlyS2 code involved. Observed in production, 2026-09.

## Tick budget

### Don't send network updates to every player every tick

**Symptom:** clients can no longer connect, and the console shows `recv queue overflow`,
`Netchan queued message new high water mark`, `SteamNetworkingSockets lock held ... thread starvation`, then
`FATAL ERROR: Watchdog timeout exceeded`.

**Cause:** a plugin updated every player's HUD on every tick. With the rest of the round-start work, the game thread
fell behind until the engine's watchdog ended the process.

**Fix:** send an update when its content changes, and throttle per player.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. Observed in production, 2026-09.

[docs-thread-safety]: https://swiftlys2.net/docs/development/thread-safety
[docs-sched-ticks]: https://swiftlys2.net/docs/development/scheduler#tick-based-timers
[sws2-threads]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-thread-management/references/threads.md
[sws2-menus]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/SKILL.md
[sws2-menus-legacy]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/references/legacy/built-in.md
[ms-cts-cancel]: https://learn.microsoft.com/en-us/dotnet/api/system.threading.cancellationtokensource.cancel
[ms-corrupted-state]: https://learn.microsoft.com/en-us/dotnet/api/system.runtime.exceptionservices.handleprocesscorruptedstateexceptionsattribute
[src-sched-repeat]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerService.cs#L123-L190
[src-sched-mapchange]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerService.cs#L15-L30
[src-sched-stoponmap]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerService.cs#L197-L200
[src-subscriber-mapunload]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventSubscriber.cs#L466-L472
[src-player-controller]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L58
[src-menus-click]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menus/MenuManagerAPI.cs#L229-L233
[src-menus-click-wasd]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menus/MenuManagerAPI.cs#L378-L382
