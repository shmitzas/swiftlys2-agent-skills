# Players and identity

Rules for player validity, identity across disconnects, bot takeover, teams and per-player state. SwiftlyS2-Skills
covers the basics: which [identity to key state by][sws2-identity], [when to initialize and release it][sws2-lifetime],
and the [guarantees][sws2-guarantees] of `IsValid` and the filtered player queries.

## Validity

### Gate join, chat, menu and disconnect paths on the controller

**Symptom:** a feature works for players who were connected when the plugin loaded, but does nothing for players who
join later: preferences revert on every join, a join-time kick or whitelist check never fires. Disconnect cleanup is
skipped and leaves per-player state behind.

**Cause:** `IPlayer.IsValid` requires a valid pawn as well as a connected, non-HLTV controller. A player has no pawn
while connecting, during team selection and often while disconnecting. `GetAllValidPlayers` and every team and alive
query filter on `IsValid`, so a loop over them skips those players too.

**Fix:** in connection, chat, menu and disconnect paths, test `player.Controller is { IsValid: true }` plus
`IsFakeClient` where needed, and iterate `GetAllPlayers`. Keep `IsValid` for spawn, damage, weapon and pawn work.

**Evidence:** [`Player.cs` L87-L92][src-player-isvalid], [`PlayerManagerService.cs` L98-L106 and
L227-L246][src-pms-collect]. Observed in production, 2026-09.

### Read a leaver's identity from the disconnect event

**Symptom:** cleanup keyed by SteamID never removes the leaver. A ready list or roster keeps players who left, and a
guard such as `if (steamId == 0) return;` turns the whole cleanup off.

**Cause:** the engine finishes its own disconnect before `OnClientDisconnected` runs, so `player.SteamID`, a live read,
already returns 0 there for an authorized player. Once the handlers return, SwiftlyS2 disposes the `IPlayer`, and its
native-backed members throw `ObjectDisposedException`. `PlayerID`, `Slot` and `SessionId` are plain values that stay
readable.

**Fix:** record the identity when you add the player to a structure, and remove by slot or session. Where the identity
is needed at disconnect, take it from `EventPlayerDisconnect`, whose payload carries `XuID`, `Name` and `NetworkID`.

**Evidence:** native [`manager.cpp` L192-L204][src-native-disconnect] and [`player.cpp` L216-L231][src-native-steamid];
[`EventPublisher.cs` L427-L449][src-publisher-disconnect], [`Player.cs` L40-L54][src-player-ids],
[`EventPlayerDisconnect.cs` L53-L77][src-gen-disconnect]. The missed leaver: observed in production, 2026-10. The
`ObjectDisposedException` once the handlers return: inferred from source, not observed.

### Key rosters by slot or session, and purge them on disconnect

**Symptom:** in a lobby with bots, a candidate list built from SteamIDs ends up empty or holds one entry for all bots.
After a disconnect, the next player in the same slot inherits the leaver's state.

**Cause:** bots report SteamID 0, and so does an unauthorized player when `SteamAuth.Mode` is `strict`. Slots are
reused by the next connection.

**Fix:** key in-match rosters by slot or `SessionId`, use the SteamID only for stored account data, and remove the
entry in the disconnect path.

**Evidence:** native [`player.cpp` L216-L231][src-native-steamid]. Observed in production, 2026-09.

## Pawns and teams

### Follow the pawn through a bot takeover

**Symptom:** after a human takes over a bot, state tied to the bot's slot stops matching: a beacon stops, a restriction
outlives the duel it belonged to, a bots-only loop rewrites the pawn the human now drives.

**Cause:** a takeover moves the human controller's `m_hPawn` to the bot's pawn; the bot controller's `m_hPlayerPawn`
still points at that pawn. `IPlayer.Pawn` follows `m_hPawn` and `IPlayer.PlayerPawn` follows `m_hPlayerPawn`.

**Fix:** key per-duel or per-effect state by a `CHandle` to the pawn and resolve the current driver with
`pawn.ToPlayer()` when you need one. In a bots-only loop, skip pawns whose driver is not a fake client.

**Evidence:** [`Player.cs` L58-L67][src-player-pawns]. Observed in production, 2026-09.

### Ask the controller which team a player is on

**Symptom:** a player who switched to spectator still counts as CT or T for minutes. Their slot stays taken, and a
replacement cannot join.

**Cause:** CS2 moves the controller to the new team at once, but a living pawn keeps its old `TeamNum` until it is
destroyed. `GetCT`, `GetT`, `GetInTeam`, `GetSpectators` and the `@ct`, `@t` and `@spec` targets all read the pawn's
team.

**Fix:** for rosters, capacity and votes, read `player.Controller.Team`. Use the pawn's team only for pawn work such as
spawns, damage and models.

**Evidence:** [`PlayerManagerService.cs` L156-L166 and L227-L262][src-pms-teams]. Observed in production, 2026-09.

## Disconnects

### Isolate each disconnect cleanup step

**Symptom:** many disconnects log their entry line and nothing after it. Rosters, votes and menus keep the player who
left.

**Cause:** one early step of the disconnect handler threw on a value that was no longer readable, and every later step
was skipped. The plugin's other handlers for the same core event are skipped too.

**Fix:** run each cleanup step in its own `try`/`catch` that logs and continues, and read only captured identity in
them.

**Evidence:** [`EventSubscriber.cs` L370-L376][src-subscriber-invoke]. The skipped steps: observed in production,
2026-10. The skipped handlers: inferred from source, not observed.

### Recompute a quorum when a voter leaves

**Symptom:** a vote cannot pass after a voter disconnects and hangs until its timer runs out, or a UI tally disagrees
with the chat line about how many votes are needed.

**Cause:** the electorate was counted once when the vote started and never shrank. Subtracting the leaver fails when
their identity is no longer readable.

**Fix:** on disconnect, recompute the electorate from live state as ballots cast plus team members who can still vote,
and resolve the vote at once if the outcome is now decided.

**Evidence:** plugin logic, no SwiftlyS2 code involved. Observed in production, 2026-10.

## Input and scoreboard

### Treat `PressedButtons` as a sample, not as input since the last check

**Symptom:** an AFK check flags players who are moving: airborne, strafing, sliding to a stop or riding a ladder.

**Cause:** `PressedButtons` returns the buttons held at the moment of the read. A check every few seconds misses any
input in between. A dead or spectating player's view angles copy the player they observe.

**Fix:** combine signals: position change for living pawns, view-angle change for living pawns only, and
`OnClientKeyStateChanged` timestamps for key edges.

**Evidence:** [`Player.cs` L69-L82][src-player-buttons]. Observed in production, 2026-09.

### Refresh the scoreboard after changing a clan tag

**Symptom:** a changed clan tag appears only after the next map change.

**Cause:** `ClanUpdated()` marks the field changed, but the client does not repaint the scoreboard for it.

**Fix:** after writing `Controller.Clan` and calling `ClanUpdated()`, fire `EventNextlevelChanged` to that player when
`Core.GameEvent.IsListeningToEvent<EventNextlevelChanged>(slot)` is true. Route every tag change through one method:
several plugins writing `Clan` overwrite each other.

**Evidence:** [`CCSPlayerController.cs` L60 and L216][src-gen-clan]; [checking event listeners][docs-listening].
Observed in production, 2026-09.

### Expect chat from clients that are not in game yet

**Symptom:** chat advertising arrives from clients that never appear in the game.

**Cause:** SwiftlyS2 creates the `IPlayer` when a client connects, and the chat path only requires that object to
exist, so a client that is still loading can send `say`.

**Fix:** record slots in `OnClientPutInServer`, drop them in `OnClientDisconnected`, and return `Stop` from a
client-command hook for `say` from any other slot. On a hot reload, seed the set from the `GetAllPlayers` entries whose
controller reports `PlayerConnectedState.Connected`.

**Evidence:** [`EventPublisher.cs` L391-L396][src-publisher-connect], native [`manager.cpp` L386-L403][src-native-say].
Inferred from source, not observed.

[docs-listening]: https://swiftlys2.net/docs/development/game-events#checking-event-listeners
[sws2-identity]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/player-state.md#choose-the-identity
[sws2-lifetime]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/player-state.md#initialize-and-release-state
[sws2-guarantees]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md#guarantees
[src-player-isvalid]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L87-L92
[src-player-ids]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L40-L54
[src-player-pawns]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L58-L67
[src-player-buttons]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L69-L82
[src-pms-collect]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/PlayerManagerService.cs#L98-L246
[src-pms-teams]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/PlayerManagerService.cs#L156-L262
[src-native-disconnect]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/manager.cpp#L192-L204
[src-native-steamid]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/player.cpp#L216-L231
[src-native-say]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L386-L403
[src-publisher-disconnect]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventPublisher.cs#L427-L449
[src-publisher-connect]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventPublisher.cs#L391-L396
[src-subscriber-invoke]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventSubscriber.cs#L370-L376
[src-gen-disconnect]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/GameEvents/Interfaces/EventPlayerDisconnect.cs#L53-L77
[src-gen-clan]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CCSPlayerController.cs#L60-L216
