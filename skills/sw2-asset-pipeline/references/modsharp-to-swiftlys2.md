# ModSharp to SwiftlyS2

Upstream's framework-specific code is ModSharp: the
[`cs2-ag2-npc-runtime`](https://github.com/AbsilDylan/cs2-skills/tree/main/cs2-ag2-npc-runtime) example project and
its Linux parameter bridge. This page maps the operations upstream asks every other framework to supply onto
SwiftlyS2 v1.5.0, and records what SwiftlyS2 already exposes for AG2 controllers. How to call each API is in
[Native Functions and Hooks][docs-native] and SwiftlyS2-Skills' [`sws2-native-and-memory`][sws2-native].

## Which upstream skills need adapting

| Upstream skill | Framework-specific content | With SwiftlyS2 |
| --- | --- | --- |
| `cs2-player-model-porting` | none | Use as is |
| `cs2-animgraph2-authoring` | none; its server-proxy step is framework-neutral | Use as is; the server side is [delivery-from-swiftlys2.md](delivery-from-swiftlys2.md) |
| `cs2-server-npc-runtime` | none; a framework-neutral scaffold whose ports a framework fills | Use as is; fill the ports with the services below |
| `source2-particle-*` | none | Use as is |
| `cs2-ag2-npc-runtime` | the ModSharp example and `linux-parameter-bridge.md` | This page |

## Upstream's operations in SwiftlyS2 v1.5.0

The first seven rows are upstream's
[Adapt Another Framework](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-ag2-npc-runtime/references/linux-parameter-bridge.md#adapt-another-framework)
table; the rest come from its engine call contract.

| Operation | ModSharp example | SwiftlyS2 v1.5.0 |
| --- | --- | --- |
| Load signatures | `IGameData.Register` | The plugin's `resources/gamedata/signatures.jsonc` (`lib`, `windows`, `linux` per name), resolved when the plugin loads ([source][src-gamedata]); read with `Core.GameData.TryGetSignature` |
| Require uniqueness | strict address resolution | Not checked in SwiftlyS2's code, which keeps whatever address its pattern scan returns ([managed][src-gamedata], [native][src-findsig]). Check uniqueness offline against the exact build |
| Transform an inner match | gamedata `factory` | Not provided: a gamedata signature resolves to its match address. Use a function-entry pattern, or upstream's bounded, validated adjustment in code |
| Validate the function entry | `ILibraryModule.GetFunctionRange` | `IMemoryService` has no function-boundary query ([source][src-memory]); validate offline |
| Spawn the body | `SpawnEntitySync<IBaseAnimGraph>` | Precache in `Core.Event.OnPrecacheResource`, then `CreateEntityByDesignerName`, a `CEntityKeyValues` carrying the model and the server-AG2 keyvalues [upstream lists][up-entity], and one `DispatchSpawn(kv)` ([entity][docs-entity], [delivery-from-swiftlys2.md](delivery-from-swiftlys2.md#spawn-a-prop-with-a-model)) |
| Schedule writes | game-frame hook | `Core.Scheduler.NextTick` or `NextWorldUpdate`, `Core.Event.OnTick` or `OnWorldUpdate`; `Core.IsGameThread` tells you where you are ([scheduler][docs-scheduler], [thread safety][docs-threads]) |
| Validate the entity | entity wrapper and native pointer | `CHandle<T>` from `Core.EntitySystem.GetRefEHandle`, which stores index and serial; check `IsValid` at call time ([entity][docs-entity]) |
| Call the native function | function pointer | A delegate with the exact calling convention, `Core.Memory.GetUnmanagedFunctionByAddress<T>(address)`, then `Call` ([native][docs-native]) |
| Turn names and ID values into engine symbols | `MakeGlobalSymbol` from tier0 | No managed wrapper. `CGlobalSymbol`'s `Value` setter stores a pointer into SwiftlyS2's own string pool ([source][src-globalsymbol], [pool][src-stringpool]), which upstream says is not a substitute. Resolve the engine function natively |

Two traps on the way:

- `IGameDataService.GetOffset` returns `int`, while `TryGetOffset` outputs `nint` ([source][src-gamedata-if]).
- SwiftlyS2 also applies byte patches from `patches.jsonc` with `ApplyPatch` ([interface][src-patch-if],
  [implementation][src-patch]). Upstream forbids patching the server binary for this work; do not use them here.

## AG2 controllers and typed parameters

Upstream asks to reuse a framework-provided typed AnimGraph setter when one exists. In SwiftlyS2 v1.5.0:

- `CBodyComponentBaseAnimGraph.AnimationController` is a typed `CBaseAnimGraphController`
  ([source][src-bodycomponent]), so reaching the controller needs no signature. Its `GraphInstanceAG2` is a
  `CAnimGraph2InstancePtr` with no members ([source][src-controller]).
- `CBaseAnimGraph.GraphControllerManager.Controllers` lists an entity's graph controllers as pointers to
  `CAnimGraphControllerBase` ([source][src-manager]). `Core.Memory.ToSchemaClass<T>` converts a pointer to a schema
  class and `GetObjectPtrVtableName` names an object's class ([source][src-memory]). This path has not been
  exercised here.
- The generated stock controller classes (`CCS2WeaponGraphController`, `CCS2PawnGraphController`,
  `CCS2ChickenGraphController`, `CCS2UIPawnGraphController`, `CDynamicPropGraphController`, `CChoreo_GraphController`)
  expose their bound parameters as `CAnimGraph2ParamOptionalRefFloat`, `...Bool` and `...CGlobalSymbol` with
  `IsValid` and a settable `Value` ([source][src-paramref]). `CDynamicPropGraphController` binds only `ActionState`
  ([source][src-dynprop]). The parameter types first appear in stable release v1.3.3 ([source][src-paramref-v133]);
  the controller classes are generated from the game's schema, and `CDynamicPropGraphController` first appears in
  stable release v1.4.11 ([source][src-dynprop-v1411]).
- Vector, Target and Transform parameters appear only as untyped fields
  ([example][src-pawncontroller]); upstream also leaves them diagnostic-only.
- An ID written through `CAnimGraph2ParamOptionalRefCGlobalSymbol.Value` goes through the same string-pool setter.
  Whether a graph's comparisons then match has not been checked.
- A custom graph's own parameters, looked up by name as upstream's example does, have no managed API. That still
  takes the native bridge from the table above.

## Entity and model rules

Upstream's spawn and model snippets are framework-neutral. In SwiftlyS2, pass the model as a spawn keyvalue, never
call `SetModel` before `DispatchSpawn`, and apply only precached paths:
[delivery-from-swiftlys2.md](delivery-from-swiftlys2.md).

[docs-native]: https://swiftlys2.net/docs/development/native-functions-and-hooks
[docs-entity]: https://swiftlys2.net/docs/development/entity
[docs-scheduler]: https://swiftlys2.net/docs/development/scheduler
[docs-threads]: https://swiftlys2.net/docs/development/thread-safety
[sws2-native]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-native-and-memory/references/interop.md
[up-entity]: https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-ag2-npc-runtime/references/entity-and-controller.md
[src-gamedata]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/GameData/GameDataService.cs#L35-L67
[src-gamedata-if]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Shared/Modules/GameData/IGameDataService.cs#L33-L47
[src-patch-if]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Shared/Modules/GameData/IGameDataService.cs#L56-L60
[src-patch]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/GameData/GameDataService.cs#L141-L177
[src-findsig]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/src/memory/gamedata/manager.cpp#L50-L55
[src-memory]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Shared/Modules/Memory/IMemoryService.cs
[src-globalsymbol]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Shared/Natives/Structs/CGlobalSymbol.cs#L13-L20
[src-stringpool]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Core/Modules/StringPool/StringPool.cs#L16-L57
[src-bodycomponent]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CBodyComponentBaseAnimGraph.cs#L18
[src-controller]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CBaseAnimGraphController.cs#L76
[src-manager]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CAnimGraphControllerManager.cs#L18
[src-paramref]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Shared/Natives/Structs/CAnimGraph2ParamOptionalRef.cs
[src-dynprop]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CDynamicPropGraphController.cs#L18
[src-paramref-v133]: https://github.com/swiftly-solution/swiftlys2/blob/v1.3.3/managed/src/SwiftlyS2.Shared/Natives/Structs/CAnimGraph2ParamOptionalRef.cs
[src-dynprop-v1411]: https://github.com/swiftly-solution/swiftlys2/blob/v1.4.11/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CDynamicPropGraphController.cs#L18
[src-pawncontroller]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.0/managed/src/SwiftlyS2.Generated/Schemas/Interfaces/CCS2PawnGraphController.cs#L54-L58
