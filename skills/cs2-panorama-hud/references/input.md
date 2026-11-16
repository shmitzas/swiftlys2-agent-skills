# HUD input

The routes a player's input can take to a custom HUD, which of them SwiftlyS2 reports, and where they collide with
play. Capture and click basics are on the official [Custom HUD][docs-hud-capture] page and in SwiftlyS2-Skills'
[integration page][sws2-clicks]; capture as per-slot state is in
[per-player-hud-state.md](per-player-hud-state.md#release-input-capture-per-slot). Checked against SwiftlyS2 v1.5.2.

Each rule gives the symptom, the cause, the fix and the evidence, and says how the rule was established: *observed in
game* in a given month, or *inferred, not observed*.

## Routes

| Route | The plugin receives | Needs | Limits |
| --- | --- | --- | --- |
| Mouse | `OnCustomHudClicked`: the player, the layout entity and the `Button` id ([docs][docs-hud-clicks]) | Input capture on for that player | Only `Button` elements report clicks. Capture puts the player in cursor mode and holds their movement until every layout releases it ([Valve][valve-capture]). A click on a layout that no longer exists is dropped before any handler runs ([source][src-click]) |
| Movement and action keys | `OnClientKeyStateChanged` for each press and release | A pawn | The [`KeyKind`][docs-keykind] keys only, and the game still acts on every key |
| Commands | A registered command, or a `HookClientCommand` handler | A key the player binds to the command, or the player typing it | Button binds never arrive as commands |
| Chat | A chat hook, or `Core.Menu`'s chat input method | The player typing | Slow, and another plugin's hook can consume the message first ([source][src-chat-dispatch]) |

Whether key states still reach the server while a layout captures input has not been established. Check it in game
before a view relies on keys and clicks together.

## Rules

### Build keyboard input from the KeyKind keys

- **Symptom:** a key the HUD listens for never produces an event, and SwiftlyS2 reports `Unknown key kind: …`.
- **Cause:** SwiftlyS2 reads the pawn's button state on each think and raises an event for every bit that changed
  ([source][src-buttons]). It maps the bits to the 19 [`KeyKind`][docs-keykind] values, and any other bit throws before
  a subscriber runs ([mapping][src-keykind], [publisher][src-keyevent]). Number keys are not among the values, and a
  player without a pawn raises no key events.
- **Fix:** take keyboard HUD input from the `KeyKind` keys. For numbers, have players bind keys to a plugin command, or
  use chat input.
- **Evidence:** the source; inferred, not observed.

### Leave movement keys to movement on plain rows

- **Symptom:** a HUD cursor moves while the player walks or strafes. By the same defaults, one press of E would both
  open a door and select a row.
- **Cause:** key states are the player's movement and action buttons: the HUD sees them, and the game still acts on
  them. `Core.Menu`'s defaults are Shift up, F down, A and D left and right, E select and Tab close
  ([source][src-core-keys]), and left and right do nothing on a plain row: only sliders and selectors take them
  ([source][src-menu-actions]). A component that made A and D jump between rows moved the cursor whenever the player
  strafed.
- **Fix:** keep A, D, W and S for sliders, selectors and movement. Bind HUD actions to keys whose game action is
  harmless while the HUD is open, and show those keys on screen.
- **Evidence:** the strafing observed in game, 2026-11; the defaults are in the source. The E case follows from the
  defaults; inferred, not observed.

### Watch for activity through key states, not a usercmd hook

- **Symptom:** server frame time grows with the player count after a HUD starts closing or updating on its player's
  activity, such as closing when the player moves.
- **Cause:** a per-command hook runs for every user command of every player: an idle check on
  `Core.GameHooks.Controller.ProcessUsercmds` took about 71% of the game thread's managed time on a production server.
  At 1.4.12, the version profiled, the hook allocated a list and a wrapper for every command
  ([1.4.12][src-usercmds-1412]). v1.5.2 rents both from pools and caches each command's `CSGOUserCmd` and
  `ButtonState` ([hook][src-usercmds], [command][src-usercmd-cache]), but nested protobuf reads still build a wrapper
  each ([getter][src-usercmd-nested]). `Core.GameHooks.Movement.RunCommand` runs per command too
  ([source][src-runcommand]) and was not measured. `OnClientKeyStateChanged` fires only when a button changes
  ([source][src-buttons]).
- **Fix:** record the time of each slot's last key-state change, compare it on a slow timer, and close or update the
  HUD from there. For the other activity signals, follow sw2-plugin-pitfalls' [`PressedButtons` rule][pitfalls-buttons].
- **Evidence:** observed in game, 2026-09, as a server profile of `ProcessUsercmds` on SwiftlyS2 1.4.12; not measured
  again on v1.5.2.

### Read button binds as key states, not client commands

- **Symptom:** a `HookClientCommand` handler waiting for `+attack2`, `+zoom` or `+use` never runs.
- **Cause:** the hook sees the console commands a player sends to the server ([docs][docs-command-hooks],
  [source][src-command-hook]). A button bind sets a bit in the user command and never arrives as a command.
- **Fix:** read `+attack2` and `+use` as the `Mouse2` and `E` key states. A button without a `KeyKind`, such as zoom,
  never reaches a key-state handler ([source][src-keykind]); read it from the user command instead
  ([sw2-plugin-pitfalls][pitfalls-binds]). Use commands only for keys that players bind to the plugin's own command.
- **Evidence:** the source; inferred, not observed. The never-matching `+attack2` and `+zoom` handler was found in a
  code review in 2026-10, not seen failing on a server.

### Translate a clicked row into a focus index

- **Symptom:** a click activates the row next to the one clicked, or the wrong item on a later page.
- **Cause:** a click reports the `Button` of a row on the page drawn, while `SetFocus` counts the focusable components
  of the whole menu ([source][src-setfocus]). Headings, text rows and progress bars shift the two apart, and a key press
  between drawing and clicking moves the focus too.
- **Fix:** when you draw a frame, record which focusable entry each Button shows: the body entries that carry a
  `MenuSelectionNode` ([frame][sws2-frame]). Resolve each click against the frame the player saw, and drop clicks for a
  frame you have replaced. The rest of the click route is in the [renderer recipe][sws2-renderer].
- **Evidence:** the source; inferred, not observed.

[docs-hud-capture]: https://swiftlys2.net/docs/development/custom-hud#input-capture
[docs-hud-clicks]: https://swiftlys2.net/docs/development/custom-hud#handling-button-clicks
[docs-keykind]: https://swiftlys2.net/docs/development/core-events#clientkind-and-keykind
[docs-command-hooks]: https://swiftlys2.net/docs/development/commands#client-command-hooks
[sws2-clicks]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/integration.md#receive-clicks
[sws2-frame]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/references/renderers.md#render-context-and-frame
[sws2-renderer]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/references/renderers.md#panorama-hud-renderer
[valve-capture]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1087-L1097
[src-click]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventPublisher.cs#L926-L943
[src-buttons]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/player.cpp#L394-L439
[src-keykind]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Misc/GameKeyKind.cs#L205-L232
[src-keyevent]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventPublisher.cs#L451-L470
[src-core-keys]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/MenuRuntimeService.cs#L57-L102
[src-menu-actions]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Menu/Input/MenuActions.cs#L27-L42
[src-command-hook]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L329-L341
[src-chat-dispatch]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Commands/CommandDispatcher.cs#L145-L163
[src-usercmds-1412]: https://github.com/swiftly-solution/swiftlys2/blob/v1.4.12/managed/src/SwiftlyS2.Core/Modules/GameHooks/Hooks/ProcessUsercmds.cs#L33-L36
[src-usercmds]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/GameHooks/Hooks/ProcessUsercmds.cs#L26-L39
[src-usercmd-cache]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/GameHooks/CUserCmd.cs#L29-L46
[src-usercmd-nested]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Protobufs/Classes/CSGOUserCmdPBImpl.cs#L15-L16
[src-runcommand]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/GameHooks/Hooks/RunCommand.cs#L10-L40
[src-setfocus]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/MenuSession.cs#L96-L113
[pitfalls-binds]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#read-key-binds-from-the-user-command-not-a-client-command-hook
[pitfalls-buttons]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#treat-pressedbuttons-as-a-sample-not-as-input-since-the-last-check
