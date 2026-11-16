# Entities, weapons and items

Rules for entity identity, networked fields, weapons and econ items. The asset skill owns the model rules: [props with
a model](../../sw2-asset-pipeline/references/delivery-from-swiftlys2.md#spawn-a-prop-with-a-model), [`SetModel` on a
live entity](../../sw2-asset-pipeline/references/delivery-from-swiftlys2.md#change-the-model-of-a-live-entity), [weapon
spawns and their subclass](../../sw2-asset-pipeline/references/delivery-from-swiftlys2.md#spawn-a-weapon-entity) and
[custom knives](../../sw2-asset-pipeline/references/delivery-from-swiftlys2.md#give-a-player-a-custom-knife).
SwiftlyS2-Skills' [entity lifetime][sws2-entities] covers spawn values and handles.

## Identity

### Hold a `CHandle` across ticks, not the entity wrapper

**Symptom:** a wrapper kept from an earlier tick still reports `IsValid` after its entity was removed, for example by
round cleanup, and writes through it land on a different entity.

**Cause:** a wrapper's `IsValid` checks that its address belongs to a live entity. An entity created later at the freed
address makes the old wrapper valid again. A `CHandle<T>` stores the index and serial number and checks both.

**Fix:** store `Core.EntitySystem.GetRefEHandle(entity)` and read `handle.Value` when you need the entity. Initialise
an unset handle with `CHandle<T>.Invalid`, not `default`: a raw value of 0 names entity index 0.

**Evidence:** [`CEntityInstanceImpl.cs` L24-L26][src-entity-isvalid], [`EntityManager.cs` L78-L86][src-entitymanager],
[`CHandle.cs` L14-L46][src-chandle]; [entity handles and safety][docs-entity-handles]. Inferred from source, not
observed.

### Track spawned props by index, not by designer name

**Symptom:** a damage or touch hook that filters on `DesignerName == "prop_dynamic_override"` never matches the props
the plugin spawned, although bullets visibly hit them.

**Cause:** after `DispatchSpawn`, a `prop_dynamic_override` reports its designer name as `prop_dynamic`.

**Fix:** keep the indices or handles of the entities you spawn and match against those. A designer-name pre-check has
to accept both names.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. Observed in production, 2026-08.

## Networking

### Re-apply transmit blocks for every joining client

**Symptom:** an entity hidden from everyone but its owner shows up for players who joined after it was hidden, or after
they reconnect.

**Cause:** `SetTransmitState(false)` sets a block for each player connected at that moment and skips empty slots. A
client starts with no blocks when it connects. SwiftlyS2 has no per-frame transmit callback that would re-evaluate
them. Blocks are kept per entity index, and SwiftlyS2 clears an index for every connected player when its entity is
deleted, so a block set later through a stored index lands on whichever entity has reused it.

**Fix:** block the restricted entities for the joining slot in `OnClientConnected`. Allow the owner by slot with
`SetTransmitState(true, slot)`. Block through a live handle, never a stored index.

**Evidence:** [`CEntityInstanceImpl.cs` L66-L87][src-entity-transmit]; native [`playermanager.cpp`
L46-L54][src-native-transmit-all], [`player.cpp` L115-L130][src-native-transmit-one], [`manager.cpp` L92-L115,
L135-L161 and L206-L235][src-native-checktransmit], [`listener.cpp` L53-L68][src-native-entity-deleted]. The leak to
joining players: observed in game, 2026-09. That `OnClientConnected` comes before the client's first snapshot, the
clearing on deletion and the block landing on a reused index: inferred from source, not observed.

### Mark the field you wrote, not its parent struct

**Symptom:** the console floods with `requested resolve all N changes, actually resolved only N-1 changes` and a
`not resolved` line for each entity the plugin writes to. At high volume the game thread stalls.

**Cause:** SwiftlyS2 generates an `*Updated()` marker for every networked field, including struct-typed ones such as
`CEconEntity.AttributeManagerUpdated()` and `CEconItemView.AttributeListUpdated()`. The engine cannot resolve a change
at the level of a struct.

**Fix:** call the marker of the scalar or collection field you changed, such as `CustomNameUpdated()` or the attribute
list's `AttributesUpdated()`, and skip the markers of struct-typed parents.

**Evidence:** generated [`CEconEntityImpl.cs` L113][src-gen-econentity] and [`CEconItemViewImpl.cs`
L204-L206][src-gen-econitem]. Observed in production, 2026-09.

### Write networked fields when they change, not every tick

**Symptom:** server memory grows by hundreds of MiB per hour for each connected player and stops when the player
leaves. The managed heap stays small, so the SwiftlyS2 profiler shows nothing.

**Cause:** a plugin wrote three scoreboard rank fields and their `*Updated()` markers for every player on every tick.
Turning that feature off stopped the growth. Throttling the writes made the rank flicker, so that feature had no
cheaper rate.

**Fix:** write a networked field and call its marker only when the value changes. If the engine keeps resetting a field
you need, find what resets it rather than re-asserting it every tick. Measure native memory, such as the container's
`anon` memory, not the managed heap. This fix has not been confirmed: the writer that kept resetting those fields was
never found.

**Evidence:** [`Schema.cs` L69-L84][src-schema-update]. Observed in production, 2026-09.

### Expect protected fields to throw while `FollowCS2ServerGuidelines` is on

**Symptom:** a skin, item-name, StatTrak or scoreboard-rank feature works on one server and throws
`Cannot get or set 0x... while "FollowCS2ServerGuidelines" is enabled` on another. `GetLoadoutItem` and the
`GetItemInLoadout` hook refuse as well.

**Cause:** while `FollowCS2ServerGuidelines` is on, which is the default in `core.jsonc`, reading or writing a listed
schema field throws. The list covers econ item IDs, the account ID, quality, level, `Initialized` and `CustomName`, the
fallback paint, seed, wear and StatTrak, econ attribute values and the competitive rank fields.

**Fix:** state the required core setting in the plugin's README. Catch the `InvalidOperationException` on the first
protected access and turn the feature off with one clear log line. The asset skill's [custom-knife
grant](../../sw2-asset-pipeline/references/delivery-from-swiftlys2.md#give-a-player-a-custom-knife) writes protected
fields.

**Evidence:** [`Schema.cs` L13-L57 and L73-L76][src-schema-protected], [`Player.cs` L255-L263][src-player-loadout];
[global settings][docs-core-config]. Inferred from source, not observed.

## Weapons

### Treat weapon VData as shared by every weapon of its class

**Symptom:** a buff meant for one player changes every weapon of that class on the server. A damage multiplier written
to `VData.Damage` changes nothing per shot. A buff that VData restoration removes at round start never comes back on
game modes that do not hand out new weapons each round.

**Cause:** every weapon of a class reads the same `CCSWeaponBaseVData`. Damage per shot did not follow writes to its
`Damage` field. `CanAcquire` does not run for a weapon a player carries into the next round, so nothing re-applies the
buff.

**Fix:** change per-shot damage in `Core.GameHooks.Entities.TakeDamage.Pre`. Keep VData changes for server-wide
settings, and after restoring VData, re-apply the buffs to the current holders on the next world update.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. The per-shot damage: observed in production, 2026-07. The lost
buff: observed in production, 2026-09.

### Leave `Clip1` alone on shell-by-shell shotguns

**Symptom:** while a plugin keeps magazines topped up, reloading a Nova, XM1014 or Sawed-Off stops after one shell.

**Cause:** writing `Clip1` during a shell-by-shell reload ends it, even when the value is capped at `MaxClip1`. Raising
`MaxClip1` in VData and writing `ReserveAmmo` did not break it. The MAG-7 reloads by magazine.

**Fix:** skip `Clip1` writes for `weapon_nova`, `weapon_xm1014` and `weapon_sawedoff`. Call `ReserveAmmoUpdated()`
after writing the reserve, or the client's reserve counter drifts during the reload.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. The stopped reload: observed in game, 2026-08. The reserve
counter drift: observed in production, 2026-09.

### Remove the weapon the player holds, not the one you expect

**Symptom:** after a weapon swap the player holds both the old and the new gun.

**Cause:** the plugin removed, by designer name, the weapon its configuration or progression said the player should
have, and the player held another.

**Fix:** strip by slot with `RemoveWeaponBySlot`, which deletes the weapon. `DropWeaponBySlot` leaves it on the ground
for anyone to pick up.

**Evidence:** [`CPlayer_WeaponServicesImpl.cs` L29-L83][src-weaponservices]. Observed in production, 2026-09.

### Clear the grenade ammo count after removing a grenade

**Symptom:** after grenades are removed and given back, the counts come out wrong, such as two flashbangs and no HE, or
the player cannot buy or pick up that grenade type for the rest of the round.

**Cause:** `RemoveWeapon` deletes the grenade entity and leaves the pawn's ammo count for its type. Buys and gives
check that count, then add to it or refuse with `ReachedGrenadeTypeLimit`.

**Fix:** after removing a grenade, set `WeaponServices.Ammo[type]` to 0 and call `AmmoUpdated()`. Take the ammo type
from `Core.Helpers.GetWeaponCSDataFromKey(definitionIndex)`; don't hard-code it. When restoring, read each type's count
once and clamp the loop that gives them back.

**Evidence:** [`CPlayer_WeaponServicesImpl.cs` L29-L37][src-removeweapon], [`AcquireResult.cs`
L9-L10][src-acquireresult]. Observed in production, 2026-10.

### Re-create a weapon from its item definition index

**Symptom:** a weapon given back to a player comes out as its sibling: a USP-S as a P2000, an M4A1-S as an M4A4, an
MP5-SD as an MP7, an R8 Revolver as a Desert Eagle.

**Cause:** these four share an entity class with another weapon, so `DesignerName` reports the shared class, and giving
that name hands out the slot's loadout default.

**Fix:** save `AttributeManager.Item.ItemDefinitionIndex`, give the weapon by
`Core.Helpers.GetClassnameByDefinitionIndex(index)`, then read the index back and correct it if it differs.

**Evidence:** [`Helpers.cs` L127-L147][src-helpers-defindex]. Observed in production, 2026-10.

### Pass item definition indices to `mp_items_prohibited`

**Symptom:** `mp_items_prohibited` set to weapon names prohibits nothing, or the previous round's prohibition stays.

**Cause:** the convar takes comma-separated item definition indices. Issued with no argument, the command prints the
current value instead of clearing it. `mp_buy_allow_guns` is a category mask, so allowing one rifle allows them all.

**Fix:** convert names with `Core.Helpers.GetDefinitionIndexByClassname`, and clear the list with
`mp_items_prohibited ""`. Gate single weapons in
[`CanAcquire`](events-and-hooks.md#block-buys-and-pickups-in-canacquire-not-after-item_purchase).

**Evidence:** [`Helpers.cs` L144-L147][src-helpers-byname]. Observed in production, 2026-10.

## Player models and items

### Clear custom gloves through their definition index

**Symptom:** an invisible or re-modelled player keeps opaque floating gloves, or a cleared glove skin comes back
mid-round.

**Cause:** gloves are an econ item on the pawn, `EconGloves`, drawn as their own attachment, so render alpha and
`SetModel` do not reach them. Setting `Initialized` to false resets the whole item and reverted a model swap. Inventory
plugins re-apply gloves on spawn and on their own commands.

**Fix:** set `EconGloves.ItemDefinitionIndex` to 0 and call `ItemDefinitionIndexUpdated()`, which falls back to the
model's own hands. Toggle the `first_or_third_person` body group off and on to make clients redraw. Re-check on a timer
while the effect lasts, and restore only onto the pawn you cleared.

**Evidence:** [`CCSPlayerPawn.cs` L94-L96][src-gen-pawn-gloves]. Observed in game, 2026-09.

### Reset aim punch together with its tick fields

**Symptom:** zeroing the recoil kick makes the view snap back for a moment between updates.

**Cause:** the client keeps interpolating from the previous base angle and tick.

**Fix:** zero the predictable angle and velocity and the unpredictable angle, set both base ticks to the current tick
and the interpolation amount to 0, each followed by its `*Updated()` call. Bullet spread is separate:
`weapon_accuracy_nospread`.

**Evidence:** [`CCSPlayer_AimPunchServices.cs` L18-L35][src-gen-aimpunch]. Observed in game, 2026-09.

## Game-owned containers and sounds

### Walk a game-owned `CUtlMap` by index

**Symptom:** the server crashes inside `CUtlRBTree.Find` when a plugin removes entries from a map the game owns.

**Cause:** `Find`, `Remove(key)`, `Insert`, `InsertOrReplace` and `Reinsert` call the comparator stored in the tree as
a managed function pointer. Only trees SwiftlyS2 builds hold one; in a game-owned tree that slot holds a native
comparator or nothing. Before v1.5.2, `RemoveAll` also broke the free list of a game-owned tree.

**Fix:** walk with `FirstInOrdered` and `NextInOrdered` collecting indices, then call `RemoveAt` for each one in a
second loop. Removing during the walk ends it early.

**Evidence:** [`CUtlRBTree.cs` L443-L499][src-rbtree], [`CUtlMap.cs` L35-L61][src-utlmap]; `RemoveAll` fixed in v1.5.2,
commit [`23fab36`][commit-rbtree]. Observed in production, 2026-10.

### Prefix custom sound-event fields with `public.`

**Symptom:** a sound emitted with `SetFloat3("position", ...)` plays at the world origin, and no error appears.

**Cause:** the sound event's fields are exposed under a `public.` prefix. A write to the bare name is dropped.

**Fix:** write `public.position` and the other custom fields with the prefix, as the sound events page does.

**Evidence:** [setting custom sound fields][docs-sound-fields]. Observed in game, 2026-08.

[docs-entity-handles]: https://swiftlys2.net/docs/development/entity#entity-handles-and-safety
[docs-core-config]: https://swiftlys2.net/docs/resources/core-config#global-settings
[docs-sound-fields]: https://swiftlys2.net/docs/development/soundevents#setting-custom-sound-fields
[sws2-entities]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-entity-management/references/entities.md
[commit-rbtree]: https://github.com/swiftly-solution/swiftlys2/commit/23fab364457fdfa3c4dbdcb39fa30ceb898bb739
[src-entity-isvalid]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CEntityInstanceImpl.cs#L24-L26
[src-entity-transmit]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CEntityInstanceImpl.cs#L66-L87
[src-entitymanager]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/EntitySystem/EntityManager.cs#L78-L86
[src-chandle]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Natives/Structs/CHandle.cs#L14-L46
[src-native-transmit-all]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/scripting/server/playermanager.cpp#L46-L54
[src-native-transmit-one]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/scripting/server/player.cpp#L115-L130
[src-native-checktransmit]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/manager.cpp#L92-L235
[src-native-entity-deleted]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/engine/entities/listener.cpp#L53-L68
[src-gen-econentity]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Schemas/Classes/CEconEntityImpl.cs#L113
[src-gen-econitem]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Schemas/Classes/CEconItemViewImpl.cs#L204-L206
[src-schema-update]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Schema.cs#L69-L84
[src-schema-protected]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Schema.cs#L13-L76
[src-player-loadout]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L255-L263
[src-weaponservices]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CPlayer_WeaponServicesImpl.cs#L29-L83
[src-removeweapon]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CPlayer_WeaponServicesImpl.cs#L29-L37
[src-acquireresult]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Misc/AcquireResult.cs#L9-L10
[src-helpers-defindex]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Helpers/Helpers.cs#L127-L147
[src-helpers-byname]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Helpers/Helpers.cs#L144-L147
[src-gen-pawn-gloves]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CCSPlayerPawn.cs#L94-L96
[src-gen-aimpunch]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CCSPlayer_AimPunchServices.cs#L18-L35
[src-rbtree]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Natives/Structs/CUtlRBTree.cs#L443-L499
[src-utlmap]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Natives/Structs/CUtlMap.cs#L35-L61
