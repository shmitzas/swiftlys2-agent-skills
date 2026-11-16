# Per-player HUD state

How a client decides which class, dialog-variable and input-capture state of a `CCSCustomHudLayout` it draws, how long
that state lives, and the SwiftlyS2 behaviour around it. The setters, getters and status values are on the official
[Custom HUD][docs-hud] page; spawning, capture basics and cleanup are in SwiftlyS2-Skills'
[integration page][sws2-integration]. Checked against SwiftlyS2 v1.5.2 and CS2 build 2000943 (2026-11-11).

Each rule gives the symptom, the cause, the fix and the evidence, and says how the rule was established: *observed in
game* in a given month, or *inferred, not observed*.

## The model

| State | Kept | Networked | Evidence |
| --- | --- | --- | --- |
| Class and dialog-variable overrides | Once globally, and once per player slot in `PlayerLayoutStates` | Per slot, through a recipients filter named `SelectOnObservableRecipientsFilter` | [schema][schema-state]; the filter from the MCP's `schema_lookup` |
| Input capture | Per slot. The global state has the field too; writing it with the global setter gave no usable cursor ([rule](#release-input-capture-per-slot)) | Per slot, through a recipients filter named `OwningSlotOnlyRecipientsFilter`: to that slot's player only, by its name | [source][src-capture]; the filter from the MCP's `schema_lookup` |
| The slot a state belongs to | `PlayerSlot` | Not networked | [schema][schema-state] |
| Panel ids, class names and variable names | One list each per entity; overrides refer to them by index | With the entity | [Custom HUD][docs-hud-state] |
| Whether the layout is observable | `Observable` | Yes | [schema][schema-layout] |

For each panel and class, or panel and variable, a client draws:

1. the entry of the slot its panel is bound to, which overrides the global value ([Valve][valve-overrides]);
2. otherwise the global value. `k_eHudPanelClassStatus_Undefined` and `RemoveDialogVariableStringForPlayer` drop a
   slot's entry, so the global value applies again;
3. with neither, for a slot never written, another player's entry (observed in game, 2026-09). For a variable removed
   from a slot while no global value exists, Valve's declaration gives an empty string instead
   ([Valve][valve-var-empty]; inferred, not observed). A class or text written in the layout file is not a global value.

SwiftlyS2 v1.5.2 has no per-player reset. The game's map scripting API has one, `ResetForPlayer`
([Valve][valve-reset]), which SwiftlyS2 does not expose.

## Resolution

### Write a global value for everything you also write per player

- **Symptom:** a player you never wrote to sees another player's state: spectators saw a teammate's menu, and players
  who had not voted saw a voter's highlight.
- **Cause:** a client with no entry for its slot draws the global value, and when the server never wrote one for that
  panel and class, the client drew another player's entry. The layout's own `hidden` class is not a global value.
- **Fix:** right after spawning the entity, write the global value of every class and variable you will ever write per
  player, for example `SetHasClass` with `k_eHudPanelClassStatus_HasClass` for a panel hidden by default. Then add the
  per-player overrides.
- **Evidence:** observed in game, 2026-09, with two accounts and a probe HUD that wrote one slot only.

### Clear a per-player class before writing the opposite status

- **Symptom:** a per-player class change has no effect after an earlier opposite write for the same panel and class: a
  HUD shown to a player while they spectated stayed visible after they respawned, although the server then hid it for
  them.
- **Cause:** not established. SwiftlyS2 v1.5.2 passes the call to the game's own `SetHasClassForPlayer`
  ([source][src-hud-classes], [signatures][src-gamefunctions]), so the update rule is the game's. The per-player getter
  returns the first matching entry.
- **Fix:** write `k_eHudPanelClassStatus_Undefined` for that panel and class, then the new status. A production plugin
  has made this double write since 2026-08.
- **Evidence:** observed in game, 2026-08.

### Pass the class status explicitly

- **Symptom:** a class disappears for a player although no code removes it.
- **Cause:** in `EHudPanelClassStatus_t`, `k_eHudPanelClassStatus_DoesNotHaveClass` is 0 and
  `k_eHudPanelClassStatus_Undefined` is `uint.MaxValue` ([source][src-status]). A `default` value or an unset field
  is therefore an explicit removal, not "leave it alone".
- **Fix:** map each state to one of the three named values in one place, and use `Undefined` only to clear.
- **Evidence:** the values are in the source; the effect in game is inferred, not observed.

## Identity

### Treat the slot as the key and clear it when the player leaves

- **Symptom:** a player who takes a slot sees its previous occupant's state: the HUD stays hidden for them, or shows
  someone else's highlight.
- **Cause:** per-player state is kept per slot, and a SwiftlyS2 player id is the slot ([source][src-player]). Nothing
  clears it when the player leaves: a write made at disconnect hid the HUD from the player who reconnected into that
  slot.
- **Fix:** when a player disconnects, undo what you wrote for the slot: `Undefined` for each class,
  `RemoveDialogVariableStringForPlayer` for each variable, and capture off. Key your own per-player data by
  `IPlayer.SessionId`, which is new for every connection ([source][src-player], [on connect][src-register],
  [lookup][src-session]), and check it against the slot's current player before a delayed write. Do not key it by
  SteamID alone: bots report 0, and so does a client that is not authenticated yet
  ([sw2-plugin-pitfalls][pitfalls-roster]).
- **Evidence:** observed in game, 2026-09, for the reconnect and for SteamID 0.

### Give a private HUD one entity per viewer

- **Symptom:** a spectator sees the menu of the player they watch. A player who opens a menu while spectating sees
  nothing, or their clicks work and nothing draws.
- **Cause:** a client binds its HUD panel to a slot when it creates the panel, the observed player's slot while it
  spectates, and does not rebind; it draws that slot's state. The per-slot lists are networked through
  `SelectOnObservableRecipientsFilter` ([model](#the-model)), and the layout has a networked `Observable` field
  ([schema][schema-layout]); whether turning `Observable` off changes this has not been tested.
- **Fix:** spawn one entity per viewer, stop transmitting it to every other player
  ([`SetTransmitState`][src-transmit]), and write its content with the global setters, which carry no slot, except
  input capture: enable and release it with `SetInputCaptureEnabledForPlayer` for the viewer's slot, even on this
  entity ([rule](#release-input-capture-per-slot)). From a connection callback, queue the spawn with
  `Core.Scheduler.NextTick` ([sw2-plugin-pitfalls][pitfalls-connect]). Per-player writes on a shared entity cannot be
  kept from a spectator whose panel is bound to that slot.
- **Evidence:** observed in game, 2026-09, with two accounts: the binding at creation, and a per-viewer entity written
  with global setters that stayed private while its owner was spectated.

### Block each joining client again

- **Symptom:** a client that connects while a private HUD exists sees it.
- **Cause:** SwiftlyS2's transmit blocks belong to each connected player ([per player][src-transmit-player]).
  `SetTransmitState(false)` blocks the entity for the players present at the call ([source][src-transmit-all]); a
  player who connects later starts with nothing blocked, because each connection registers a new player object
  ([connect][src-client-connect], [register][src-register-player]) whose blocks start empty
  ([member][src-blocked-bits]).
- **Fix:** when a client connects, block every private entity it must not see, as early as `OnClientConnected`
  ([sw2-plugin-pitfalls][pitfalls-transmit]). SwiftlyS2 clears every connected player's block on an index when that
  entity is deleted ([source][src-transmit-delete]); block through a live handle, never a stored index.
- **Evidence:** the leak observed in game, 2026-09; the cause and the clearing on deletion are in the source. That
  blocking at `OnClientConnected` comes early enough is inferred, not observed.

### Re-create rather than repaint when one client draws nothing

- **Symptom:** one client, often one who joined after the HUD was spawned, sees nothing, while the server's writes
  succeed and other players see the HUD.
- **Cause:** not established. Rule out a stale entry for the slot and a panel bound while spectating (rules above). In a
  production plugin, a shared HUD spawned before a client connected stayed invisible to that client until the entity
  was re-created; in another case the same month, a client that connected while a menu was open drew it.
- **Fix:** re-create the entity while the client is connected, then re-apply its state; from a connection callback,
  queue it with `Core.Scheduler.NextTick` ([sw2-plugin-pitfalls][pitfalls-connect]). Writing more state to the
  existing entity did not help.
- **Evidence:** observed in game, 2026-09; the cause is inferred, not observed.

## Lifetime and threads

### Re-apply everything to a new entity

- **Symptom:** after a round restart, a map change or any re-creation of the entity, the HUD is gone or shows its
  authored state: classes and texts written earlier are lost.
- **Cause:** state belongs to the entity, and a new entity starts from the layout as authored. A round restart
  (`mp_restartgame`) removed plugin-spawned layout entities, and one production plugin saw them removed at the start of
  every round. A new entity also starts with input capture off ([integration][sws2-clicks]).
- **Fix:** keep the state you show in plugin memory and check the entity's handle before each write. When you create an
  entity, re-apply everything in order: global values, per-player overrides, then capture for interactions still open.
  Keep timers and "shown until" deadlines across a re-creation: a new entity changes what is drawn, not what is pending.
- **Evidence:** observed in game, 2026-09. That a new entity starts with input capture off comes from SwiftlyS2-Skills'
  integration page; not observed.

### Release input capture per slot

- **Symptom:** a player keeps a cursor and cannot move after a HUD closes, or has no usable cursor although capture was
  set.
- **Cause:** only `SetInputCaptureEnabledForPlayer` calls the game's own setter ([source][src-capture],
  [signatures][src-gamefunctions]), the per-slot call that forces a player into cursor mode ([Valve][valve-capture]).
  The global `SetInputCaptureEnabled` only writes the global state's field, and Valve's API has no global capture. The
  player gets movement back only once every layout has turned capture off for them ([Valve][valve-capture]). Capture
  is kept per slot and sent to that slot's player alone ([model](#the-model)), so capture left on stays with the slot,
  and a layout entity created afterwards starts without it.
- **Fix:** enable and release capture with `SetInputCaptureEnabledForPlayer` for the player's slot, also on a
  per-viewer entity that you write with the global setters. When to turn it on and off is on SwiftlyS2-Skills'
  [integration page][sws2-integration].
- **Evidence:** with `SetInputCaptureEnabledForPlayer` on menus transmitted to their owner only, a usable cursor
  observed in game, 2026-11: a production plugin's lists scrolled under it. With the global setter on such menus, no
  usable cursor, observed in game, 2026-09. Why is in the source and Valve's declarations. The stuck cursor, capture
  staying with the slot and a new entity starting without it are inferred, not observed.

### Write on the game thread and batch writes from elsewhere

- **Symptom:** a HUD stops updating while chat output from the same code keeps working, and an
  `InvalidOperationException` ("This method can only be called from the main thread.") is logged or swallowed.
- **Cause:** every synchronous setter checks the thread and throws off it ([setter][src-hud-setters],
  [check][src-mainthread]). Code after an `await` can resume off it ([docs][docs-thread-unsafe]), and a menu
  renderer's `Render` runs off it ([docs][docs-render-thread], [source][src-render-worker]). Each `…Async` setter runs
  inline on the game thread and otherwise schedules its own next-tick call ([`QueueOrNow`][src-queueornow]). The
  getters have no thread check and read the entity's memory directly ([getters][src-hud-getters]).
- **Fix:** call the synchronous setters on the game thread. Elsewhere, collect a frame's writes and apply them in one
  `Core.Scheduler.NextTick` rather than one `…Async` call each, and read the getters on the game thread only.
  General rules are in [Thread Safety][docs-thread] and sw2-plugin-pitfalls' [threads page][pitfalls-threads].
- **Evidence:** the throw is in the source. The swallowed exception observed in game, 2026-09, came from a wrapper
  plugin's own thread check; with the SwiftlyS2 setters it is inferred from the source, not observed. Getter races are
  inferred, not observed.

[docs-hud]: https://swiftlys2.net/docs/development/custom-hud
[docs-hud-state]: https://swiftlys2.net/docs/development/custom-hud#layout-state
[docs-thread]: https://swiftlys2.net/docs/development/thread-safety#dispatching-to-the-main-thread
[docs-thread-unsafe]: https://swiftlys2.net/docs/development/thread-safety
[docs-render-thread]: https://swiftlys2.net/docs/development/menu-system#implementing-imenurenderer
[sws2-integration]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/integration.md
[sws2-clicks]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/integration.md#receive-clicks
[schema-layout]: https://swiftlys2.net/schema-viewer/cs2/server/CCSCustomHudLayout
[schema-state]: https://swiftlys2.net/schema-viewer/cs2/server/CCSCustomHudLayoutState
[valve-overrides]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1068-L1086
[valve-var-empty]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1083-L1086
[valve-capture]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1087-L1097
[valve-reset]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1098-L1105
[src-hud-setters]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CCSCustomHudLayoutImpl.cs#L53-L63
[src-hud-getters]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CCSCustomHudLayoutImpl.cs#L86-L100
[src-hud-classes]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CCSCustomHudLayoutImpl.cs#L134-L175
[src-capture]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CCSCustomHudLayoutImpl.cs#L209-L229
[src-gamefunctions]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Natives/GameFunctions.cs#L116-L121
[src-status]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Schemas/Enums/EHudPanelClassStatus_t.cs#L7-L12
[src-player]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L21-L43
[src-register]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventPublisher.cs#L391-L396
[src-session]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Players/IPlayerManager.cs#L319-L333
[src-transmit]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CEntityInstanceImpl.cs#L66-L87
[src-transmit-all]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/scripting/server/playermanager.cpp#L46-L54
[src-transmit-player]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/scripting/server/player.cpp#L115-L130
[src-transmit-delete]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/engine/entities/listener.cpp#L53-L68
[src-client-connect]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/manager.cpp#L135-L144
[src-register-player]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/manager.cpp#L206-L221
[src-blocked-bits]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/player.h#L91
[src-render-worker]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/MenuRenderWorker.cs#L20-L41
[src-mainthread]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Natives/NativeBinding.cs#L11-L17
[src-queueornow]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L392-L401
[pitfalls-roster]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#key-rosters-by-slot-or-session-and-purge-them-on-disconnect
[pitfalls-transmit]: ../../sw2-plugin-pitfalls/references/entities-and-weapons.md#re-apply-transmit-blocks-for-every-joining-client
[pitfalls-connect]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#create-entities-a-tick-after-a-client-connects
[pitfalls-threads]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md
