# Events and hooks

Rules for core events, game events, typed game hooks and the CS2 round flow. SwiftlyS2-Skills' [events and
hooks][sws2-events] covers registration ownership, hook phases and payload lifetime, and the official pages cover
[attributes][docs-attributes] and [game events][docs-game-events-hooking].

## Registration

### Register handler classes other than the plugin class

**Symptom:** the plugin loads with a clean log, and the attribute handlers on a module, feature or round class never
run.

**Cause:** SwiftlyS2 scans only the plugin instance for attributes. Any other instance is scanned when it is passed to
`Core.Registrator.Register`, and registering the same instance again duplicates every handler on it.

**Fix:** call `Core.Registrator.Register(instance)` once per instance, in `Load`. Never call it from
`UseSharedInterface` or `OnSharedInterfaceInjected`, which run again on every plugin load and unload.

**Evidence:** [`PluginManager.cs` L872-L877][src-pm-instantiate], [`RegistratorService.cs` L15-L25][src-registrator];
[registration scope][docs-registration-scope]. Observed in production, 2026-10.

### Take a game-hook context by `ref`

**Symptom:** a `[GameHookHandler]` method never runs, and nothing is logged.

**Cause:** the attribute parser skips a method whose first parameter is not passed by `ref`, or whose context type is
not a known hook. A mismatched `[GameEventHandler]`, `[EventListener<T>]` or `[Command]` method throws at registration
instead.

**Fix:** declare the handler exactly as the hook's delegate, for example
`void OnTakeDamage(ref TakeDamageEntityPreContext ctx)`.

**Evidence:** [`GameHooksAttributeParser.cs` L48-L71][src-gamehook-parser], [`GameEventAttributeParser.cs`
L18-L20][src-gameevent-parser]; [signature rules][docs-signature-rules]. Inferred from source, not observed.

### Catch exceptions inside each core-event handler

**Symptom:** after one handler throws, the plugin's other handlers for the same core event skip that call, so cleanup
on disconnect or map change only half happens.

**Cause:** a plugin's handlers for one core event form a single multicast delegate that SwiftlyS2 invokes inside one
`try`. The first exception ends the call for every handler after it.

**Fix:** wrap each handler's body in its own `try`/`catch`, and split long cleanups into steps that fail independently
([disconnect cleanup](players-and-identity.md#isolate-each-disconnect-cleanup-step)).

**Evidence:** [`EventSubscriber.cs` L370-L376][src-subscriber-invoke]. Inferred from source, not observed.

## Results and suppression

### Return `Stop` or `CancelOriginal` to block an action

The official [hook modes and results][docs-hook-results] table covers this: `Handled` stops the later hooks, not the
original.

### Don't expect event suppression to hide game-state UI

**Symptom:** setting `DontBroadcast` on `bomb_planted`, or blocking user messages, leaves the "bomb has been planted"
alert on every client's screen.

**Cause:** the client builds that alert from replicated game-rules state and its own localization, not from the event
or a message the server sends.

**Fix:** leave the event alone and move the plugin's own UI out of the alert's way. HUD placement is in this pack's
[`cs2-panorama-hud`](../../cs2-panorama-hud/SKILL.md) skill.

**Evidence:** [firing events][docs-firing-events] (what `DontBroadcast` does). Observed in game, 2026-09.

## Event payloads

### Read `player_hurt` values from the `Actual*` members

**Symptom:** remaining health reads wrong once a player has more than 255 health, as in modes with boosted health, and
large damage values wrap.

**Cause:** the obsolete `Health`, `Armor`, `DmgArmor` and `HitGroup` members of `EventPlayerHurt` cast the event's
integer to `byte`, and `DmgHealth` casts it to `short`. Using them compiles with only an obsolete warning.

**Fix:** read `ActualHealth`, `ActualArmor`, `ActualDmgHealth`, `ActualDmgArmor` and `ActualHitGroup`, and treat an
obsolete warning on a game-event member as a bug.

**Evidence:** generated [`EventPlayerHurt.cs` L70-L160][src-gen-playerhurt] and [`EventPlayerHurtImpl.cs`
L52-L94][src-gen-playerhurt-impl]. Inferred from source, not observed.

## Typed game hooks

### Block buys and pickups in `CanAcquire`, not after `item_purchase`

**Symptom:** restricted weapons still reach players. Ctrl+buying for a teammate drops the weapon on the ground, buying
twice drops the first gun, and stripping weapons after `item_purchase` removes ones the player was given legitimately.

**Cause:** `item_purchase` reports a buy that already happened, and a Ctrl+buy never lands in the buyer's inventory.

**Fix:** refuse in `Core.GameHooks.Items.CanAcquire.Pre`, which runs before the item exists:

```csharp
Core.GameHooks.Items.CanAcquire.Pre += (ref CanAcquireItemPreContext ctx) =>
{
    if (!IsRestricted(ctx.Params)) return; // AcquireMethod, WeaponVData.GearSlot, EconItemView
    ctx.SetReturn(AcquireResult.NotAllowedByProhibition);
    ctx.SetHookResult(HookResult.Stop);
};
```

The plugin's own `GiveItem` calls pass through the same hook as pickups, so an allow-list there also blocks the
plugin's own allocation. Refuse pickups silently: standing on a weapon repeats the check every tick.

**Evidence:** [`ICanAcquireItem.cs` L7-L28][src-canacquire], [`AcquireMethod.cs` L3-L8][src-acquiremethod]. Observed in
production, 2026-10.

### Read the attacking pawn from `AttackerInfo`

**Symptom:** a damage hook that checks `Info.Attacker.Value is CCSPlayerPawn` skips most gun damage, so a damage buff
never applies.

**Cause:** `Info.Attacker` is a `CHandle<CEntityInstance>` that can resolve to an entity other than the attacker's
pawn. `Info.AttackerInfo.AttackerPawn` is a `CHandle<CCSPlayerPawn>`.

**Fix:**

```csharp
Core.GameHooks.Entities.TakeDamage.Pre += (ref TakeDamageEntityPreContext ctx) =>
{
    var attacker = ctx.Params.Info.AttackerInfo.AttackerPawn.Value;
    if (attacker is null) return;
    ctx.Params.Info.Damage *= MultiplierFor(attacker);
};
```

**Evidence:** [`CTakeDamageInfo.cs` L9-L15 and L29-L56][src-takedamageinfo]. Observed in production, 2026-07.

### Don't expect `OnClientKeyStateChanged` to report every key

**Symptom:** a key-state handler never sees some keys, such as zoom or use-or-reload, and the server logs an exception
on each of those presses.

**Cause:** SwiftlyS2 converts the native button to a `KeyKind` before calling any handler. Buttons without a `KeyKind`
throw there, so no handler in any plugin receives them.

**Fix:** rely only on the keys the core events page lists. Read any other button from the user command in
`Core.GameHooks.Movement.RunCommand.Pre`.

**Evidence:** [`EventPublisher.cs` L451-L470][src-publisher-keys], [`GameKeyKind.cs` L206-L231][src-tokeykind];
[`KeyKind` values][docs-keykind]. Inferred from source, not observed.

## Client connection callbacks

### Create entities a tick after a client connects

**Symptom:** the server crashes the moment a player finishes connecting. The managed trace ends in a native call under
the plugin's `OnClientPutInServer` handler.

**Cause:** `OnClientPutInServer` runs inside the engine's own client callback, and creating and spawning entities there
crashed. The `if (!Core.IsGameThread) NextTick(...) else ...` branch from the thread-safety page picks a thread, not a
moment: an engine callback is already on the game thread, so the branch always runs the work inline.

**Fix:** queue entity creation from connection callbacks with `Core.Scheduler.NextTick` unconditionally, and resolve
the player again by slot or session inside the queued callback.

**Evidence:** [`EventPublisher.cs` L472-L492][src-publisher-putinserver]; thread safety [core rule][docs-thread-core].
Observed in production, 2026-09.

## Rounds and match flow

### Expect `round_announce_match_start` every round in some modes

**Symptom:** per-match state resets each round, or a vote or timer keyed to the match start never fires.

**Cause:** with `mp_ignore_round_win_conditions 1`, CS2 raises the event at every round end, not once per match.

**Fix:** treat the event as "the round restarted", keep the match phase in your own state, and do not reset that state
in a `catch` block when a read fails once.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. Observed in production, 2026-07.

### Apply a pause after the round restart, not next to it

**Symptom:** a phase that should run paused, such as a team pick, runs live. A forced round end during a match does
nothing.

**Cause:** a `mp_restartgame N` that an executed cfg schedules clears a pause issued next to the `exec` when the
restart lands. `TerminateRound` does nothing while the warmup period is still set, even if the plugin considers the
match started.

**Fix:** re-apply the pause from a `round_prestart` pre hook while the phase lasts. End warmup before calling
`TerminateRound`, and treat a call made during warmup as failed.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. Observed in production, 2026-09.

### Keep large cfg files out of round transitions

**Symptom:** the server freezes for one to four seconds at the same transition every match, and every connected client
logs `high frame misdelivery` at that moment.

**Cause:** executing a cfg that set 112 cvars stalled the game thread on every run. Cfgs of 36 to 41 cvars at the other
transitions did not.

**Fix:** move cvars that do not change between phases into a cfg executed once per map, and keep transition cfgs to the
values that change. Whether this split removed the stall has not been confirmed.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. Observed in production, 2026-09.

[docs-attributes]: https://swiftlys2.net/docs/development/using-attributes
[docs-registration-scope]: https://swiftlys2.net/docs/development/using-attributes#registration-scope
[docs-signature-rules]: https://swiftlys2.net/docs/development/using-attributes#signature-rules
[docs-game-events-hooking]: https://swiftlys2.net/docs/development/game-events#hooking-events
[docs-firing-events]: https://swiftlys2.net/docs/development/game-events#firing-events
[docs-hook-results]: https://swiftlys2.net/docs/development/native-functions-and-hooks#hook-modes-and-results
[docs-keykind]: https://swiftlys2.net/docs/development/core-events#clientkind-and-keykind
[docs-thread-core]: https://swiftlys2.net/docs/development/thread-safety#core-rule
[sws2-events]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/events-hooks.md
[src-pm-instantiate]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L872-L877
[src-registrator]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/RegistratorService.cs#L15-L25
[src-gamehook-parser]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/AttributeParsers/GameHooksAttributeParser.cs#L48-L71
[src-gameevent-parser]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/AttributeParsers/GameEventAttributeParser.cs#L18-L20
[src-subscriber-invoke]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventSubscriber.cs#L370-L376
[src-gen-playerhurt]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/GameEvents/Interfaces/EventPlayerHurt.cs#L70-L160
[src-gen-playerhurt-impl]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/GameEvents/Classes/EventPlayerHurtImpl.cs#L52-L94
[src-canacquire]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/GameHooks/HooksCategories/Items/ICanAcquireItem.cs#L7-L28
[src-acquiremethod]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Misc/AcquireMethod.cs#L3-L8
[src-takedamageinfo]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Natives/Structs/CTakeDamageInfo.cs#L9-L56
[src-publisher-keys]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventPublisher.cs#L451-L470
[src-tokeykind]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Misc/GameKeyKind.cs#L206-L231
[src-publisher-putinserver]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventPublisher.cs#L472-L492
