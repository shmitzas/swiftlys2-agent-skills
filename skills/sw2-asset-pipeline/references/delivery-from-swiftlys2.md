# Deliver custom models from a SwiftlyS2 plugin

How to precache, spawn, swap and grant custom models from a SwiftlyS2 plugin without crashing the server, and what
each route has been seen to do on clients. Checked against SwiftlyS2 v1.5.0.

SwiftlyS2-Skills already covers the precache event and logical paths ([`sws2-game-assets`][sws2-assets]) and the
general spawn flow ([`sws2-entity-management`][sws2-entities]). This page adds the steps specific to custom models.
Look up exact declarations through the SwiftlyS2 MCP or [swiftlys2.net][docs]; the snippets show usage only. If the
MCP is unreachable, download a fresh copy of [`llms-full.txt`][docs-llms-full] and search it rather than reading it
whole; each docs page in it starts at a line beginning `## https://swiftlys2.net/docs`. It has no API reference, so
take exact declarations from the SwiftlyS2 source at the tag of the package version your plugin builds with.

## What each route has been seen to do

| Route | Seen |
| --- | --- |
| Prop spawned with the model as a spawn keyvalue | In production plugins, without the crash below (2026) |
| `SetModel` on a new prop before `DispatchSpawn` | Crashed production servers on skeletal models with the `SetupModel` assertion (2026-08) |
| Weapon entity spawned without a `ChangeSubclass` first | Crashed the server inside `Spawn` (2026-09) |
| Weapon entity with `ChangeSubclass` sent before `DispatchSpawn` | Spawned; one non-fatal `SetupModel` assertion in the console (2026-09) |
| Custom knife granted by a plugin, subclass and item definition index both 42 | Custom model drawn on default-knife animations, in production |
| The same grant with 500 or 515 | Implemented; not seen in game |
| Custom knife from a map `point_script`, no subclass change | Custom model drawn on default-knife animations (2026-11-06, 2026-11-12) |
| Map `point_script` that sends `ChangeSubclass 500` or `515` | The other knife's animations, drawn on the stock default knife (2026-11-06, 2026-11-12). On 2026-11-06 the server still reported the custom model |
| Grenade model swap on a stock `weapon_decoy`, killfeed icon by weapon name | Designed and compiled; not run in game |

## Precache and pin the path

1. Subscribe to `Core.Event.OnPrecacheResource` in `Load` ([core events][docs-core-events]).
2. In the handler, check that the compiled file is in the mounted content, add the path, and keep it in a field for
   this map. `AddItem` adds the path to the engine's resource manifest ([interface][src-precache-if],
   [implementation][src-precache-impl]).

   ```csharp
   private string? knifeModel; // the path precached for this map, or null

   private void OnPrecacheResource(IOnPrecacheResourceEvent e)
   {
       knifeModel = null;
       var path = config.KnifeModel; // e.g. "weapons/custom/knife/example_butterfly/example_butterfly.vmdl"
       if (string.IsNullOrWhiteSpace(path) || !Core.GameFileSystem.FileExists(path + "_c", "GAME"))
           return;
       e.AddItem(path);
       knifeModel = path;
   }
   ```

3. Apply models only from that field, never straight from configuration. Configuration can reload at runtime
   ([configuration][docs-config]), and production plugins never `SetModel` a path that was not precached, on the
   assumption that it crashes the server; that crash has not been observed. A path added mid-map waits for the next
   map.
4. Do not read more into the check than it gives. `FileExists` proves that the compiled file is on disk;
   `PrecacheFile` is the other probe [`IGameFileSystem`][src-filesystem] offers. Neither proves that the model loads
   on the current build ([compile-and-inspect.md](compile-and-inspect.md#inspect-the-compiled-model)).

## Spawn a prop with a model

Pass the model as a spawn keyvalue ([entity][docs-entity], [entity key values][docs-ekv]):

```csharp
var prop = Core.EntitySystem.CreateEntityByDesignerName<CBaseModelEntity>("prop_dynamic_override");
prop.Teleport(origin, angles, Vector.Zero);
using var kv = new CEntityKeyValues();
kv.SetString("model", knifeModel!); // a path precached for this map
prop.DispatchSpawn(kv);
```

- Never call `SetModel` before `DispatchSpawn`. On a skeletal model it trips
  `Assertion Failed in function SetupModel(): 0 == ( pInstance->GetOwnerEntity()->GetEntityIdentity()->GetFlags() & EF_IN_STAGING_LIST )`
  and took production servers down. Whether a model is skeletal depends on how it was compiled, not on its name.
- Production plugins got props without collision hulls when the model came from `SetModel` instead of the spawn
  keyvalue. The keyvalue route keeps them.

## Change the model of a live entity

- `SetModel` is `[ThreadUnsafe]` and throws when called off the game thread ([interface][src-bme-if],
  [implementation][src-bme-impl]).
- `SetModelAsync` is `QueueOrNow(() => SetModel(model))`. Called on the game thread, it runs `SetModel` inline and
  returns a completed task; called from another thread, it queues the call for the next tick
  ([`QueueOrNow`][src-queueornow]). It never defers a call made on the game thread.
- To apply a model one tick later, schedule it yourself ([scheduler][docs-scheduler]) and re-check the entity
  through a handle:

  ```csharp
  var handle = Core.EntitySystem.GetRefEHandle(entity);
  Core.Scheduler.NextTick(() =>
  {
      if (handle.IsValid)
          handle.Value!.SetModel(knifeModel!);
  });
  ```

## Spawn a weapon entity

For a weapon that stands in the world, such as a display piece, rather than one given to a player:

```csharp
var weapon = Core.EntitySystem.CreateEntityByDesignerName<CCSWeaponBase>("weapon_knife");
weapon.AcceptInput("ChangeSubclass", "515"); // before DispatchSpawn
using var kv = new CEntityKeyValues();
kv.SetVector("origin", origin);
kv.SetQAngle("angles", angles);
weapon.DispatchSpawn(kv);
```

- Send `ChangeSubclass` before `DispatchSpawn`, for knives too. Every knife is a `weapon_knife` whose identity is
  its subclass, and a weapon spawned without one crashed the server inside `Spawn` (2026-09).
- Use `AcceptInput`. `AcceptInputAsync` is `QueueOrNow` as well ([source][src-acceptinput]): the same call on the
  game thread, and from any other thread queued to the next tick, after the spawn.
- The spawned weapon is a world item: it falls and players can pick it up (seen 2026-09).

## Give a player a custom knife

Clients appear to pick a knife's model from its econ item definition index: in every observed case they drew the
server-side model only while the knife's subclass matched that index, whatever model name the server reported
([what each route has been seen to do](#what-each-route-has-been-seen-to-do)). Upstream records the same split for
weapons in general: a server `SetModel` alone does not establish what the owner sees
([weapon presentation contracts][up-presentation]). Set the subclass and the index together, in one game-thread
call:

1. Remove the current knife, matched by weapon type. `RemoveWeaponBySlot(GEAR_SLOT_KNIFE)` removes every weapon whose
   gear slot is the knife slot ([source][src-removebyslot]); a production plugin matches by type because the taser
   shares that slot.
2. Give a fresh `weapon_knife` with `ItemServices.GiveItem<CCSWeaponBase>("weapon_knife")`.
3. Send `ChangeSubclass` with the item definition index N.
4. Set `AttributeManager.Item.ItemDefinitionIndex` to N and `Initialized` to true, each followed by its `Updated()`
   call ([`CEconItemView`][src-econitem]).
5. Apply the precached model. The production route calls `SetModelAsync` on the game thread, which runs inline, so
   the model is set in the grant tick.
6. Write `CustomName` and `CustomNameOverride` and call `CustomNameUpdated()` in the same tick. A paint written after
   the client had received the item did not reliably show (seen in production), and the name is the same kind of
   econ write.

```csharp
// Game thread. index: 42 for the default knife, or the knife whose animations the model rides.
var knife = pawn.ItemServices!.GiveItem<CCSWeaponBase>("weapon_knife");
knife.AcceptInput("ChangeSubclass", index.ToString(CultureInfo.InvariantCulture));
var item = knife.AttributeManager.Item;
item.ItemDefinitionIndex = index;
item.ItemDefinitionIndexUpdated();
item.Initialized = true;
item.InitializedUpdated();
knife.SetModel(knifeModel!); // SetModelAsync makes the same call inline on the game thread
item.CustomName = "Example butterfly";
item.CustomNameOverride = "Example butterfly";
item.CustomNameUpdated();
```

With index 42 this route draws the custom model on default-knife animations in production. With 500 or 515, which a
model on the bayonet or butterfly frame needs for its own animations, it is implemented but has not been seen in game.

If an inventory-skin plugin runs on the same server, it has to leave this knife alone, or it re-gives or repaints
it: have it ask the granting plugin, for example through a shared interface, before any knife write. The granting
plugin then makes the knife writes the skin plugin would have made, without the paint, so that a real StatTrak
counter or paint cannot land on the model's copied `stattrak` attachment:

- clear `AttributeList` and `NetworkedDynamicAttributes` (`Attributes.RemoveAll()`, then `AttributesUpdated()`);
- give the item a fake `ItemID` below the skin plugin's range (one production plugin counts up from 32768), with
  `ItemIDLow` and `ItemIDHigh`;
- set `AccountID` to the owner and `EntityQuality` to 0, each with its `Updated()` call.

## Test with a map script

[`give_example_butterfly.js`](../scripts/examples/custom_knife/give_example_butterfly.js) gives every player the
example knife on spawn. It is a test harness, not a delivery route.

1. Build and compile the knife into your addon.
2. Copy the script into the content addon's `maps/scripts/`.
3. In Hammer, add a `point_script` entity whose `cs_script` is `maps/scripts/give_example_butterfly.vjs`, and build
   the map.
4. Set `CONVERT_TO_BUTTERFLY`, load the map with the addon mounted, and spawn.
5. Remove the entity before publishing the map, or every player spawns with the knife.

What it showed on 2026-11-12, repeating a 2026-11-06 run with a knife on the bayonet frame:

| `CONVERT_TO_BUTTERFLY` | Animations | Clients draw |
| --- | --- | --- |
| `false` | default knife | the example model |
| `true` (`ChangeSubclass 515`) | butterfly | the stock default knife |

- A map script can `SetModel` and fire `ChangeSubclass`, but it cannot write the item definition index, so a map
  cannot pair a custom model with another knife's animations. `GiveNamedItem("weapon_bayonet")` gave nothing
  (2026-11-06). The cs_script API ships with the Workshop Tools as
  `<CS2>/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts`.
- Hammer's `game_player_equip` and spawn loadouts take item class names, not model paths.
- The server-side line the harness logs was not recorded on 2026-11-12. On 2026-11-06 the server still reported the
  custom model while clients drew the stock knife.
- Whether the butterfly animations move the example's blade, rear and lock bones needs the plugin route with
  index 515.

## Swap a grenade's models

A design for a custom throwable on the stock decoy. It is compiled, not run in game.

1. Keep a stock `weapon_decoy` as the proxy: no `ChangeSubclass` and no `weapons.vdata` change.
2. Give it, then set the held model with `Core.Scheduler.NextTick`. The design defers to the next tick on purpose;
   `SetModelAsync` would not defer on the game thread.
3. In `Core.Event.OnEntityCreated`, watch for `decoy_projectile`. A tick later, read its `Thrower`
   ([`CBaseGrenade`][src-grenade]), and if the thrower is armed with the custom throwable, `SetModel` the projectile
   model. That model needs a `decoy_particle` attachment and a `thrown` sequence
   ([weapon-frames.md](weapon-frames.md#grenade-on-the-decoy-frame)).
4. Expect the HUD slot to keep the decoy icon: it follows the proxy's item definition, and a Workshop addon cannot
   add item definitions.
5. For a killfeed icon per throwable, hook `EventPlayerDeath` in `Pre` mode ([game events][docs-game-events]) and set
   its `Weapon` ([settable][src-playerdeath]) to the icon's name when the kill came from the throwable. Ship
   `panorama/images/icons/equipment/<name>.vsvg_c` from that folder, added to the pack list
   ([compile-and-inspect.md](compile-and-inspect.md#pack-for-the-workshop)). Overriding the stock decoy's own icon
   instead would change every decoy wherever the addon is mounted ([upstream][up-packer]).

[docs]: https://swiftlys2.net
[docs-llms-full]: https://swiftlys2.net/llms-full.txt
[docs-core-events]: https://swiftlys2.net/docs/development/core-events
[docs-config]: https://swiftlys2.net/docs/development/configuration
[docs-entity]: https://swiftlys2.net/docs/development/entity
[docs-ekv]: https://swiftlys2.net/docs/development/entitykeyvalues
[docs-scheduler]: https://swiftlys2.net/docs/development/scheduler
[docs-game-events]: https://swiftlys2.net/docs/development/game-events
[sws2-assets]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-game-assets/references/assets.md
[sws2-entities]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-entity-management/references/entities.md
[src-precache-if]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Shared/Modules/Events/EventParams/IOnPrecacheResourceEvent.cs
[src-precache-impl]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/Events/EventParams/OnPrecacheResourceEvent.cs#L12-L14
[src-filesystem]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Shared/Modules/FileSystem/IGameFileSystem.cs#L35-L83
[src-bme-if]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CBaseModelEntity.cs#L31-L44
[src-bme-impl]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CBaseModelEntityImpl.cs#L19-L28
[src-queueornow]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L392-L401
[src-acceptinput]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CEntityInstanceImpl.cs#L36-L49
[src-removebyslot]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CPlayer_WeaponServicesImpl.cs#L69-L83
[src-econitem]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CEconItemView.cs
[src-playerdeath]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/GameEvents/Interfaces/EventPlayerDeath.cs#L103-L108
[src-grenade]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CBaseGrenade.cs#L42
[up-presentation]: https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/weapon-presentation-contracts.md#1-separate-presentation-surfaces-and-identity
[up-packer]: https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/workshop-runtime-and-debugging.md#2-packer-roots-and-gameinfo
