---
name: sw2-asset-pipeline
description: >-
  Build CS2 models that have no source asset (props, map decorations, custom knives on stock knife animations,
  custom grenades on the stock decoy, pickup piles) procedurally in Blender as hand-written SMD and DMX or as FBX for
  ModelDoc, compile and inspect them with resourcecompiler and Source2Viewer-CLI, and deliver them from a SwiftlyS2
  plugin. Routes CS:GO and AG1 model porting, AnimGraph2, NPC and particle work to the upstream cs2-skills. Use when a
  task mentions a custom knife or grenade model, a Blender-built prop, VMDL, SMD, DMX hulls, hitboxes, FBX import
  scale, a stock weapon frame, a Workshop addon that misses or shadows files, a custom knife drawn as the stock knife,
  ChangeSubclass or the item definition index, SetModel crashes or SetupModel EF_IN_STAGING_LIST asserts, precaching
  or spawning a prop with a model, or porting ModSharp asset code to SwiftlyS2.
---

# SwiftlyS2 asset pipeline

Builds Counter-Strike 2 models from nothing, compiles and inspects them, and gets them in front of players from a
SwiftlyS2 plugin. Porting existing assets, AnimGraph2, NPCs and particles belong to the upstream
[cs2-skills](https://github.com/AbsilDylan/cs2-skills). This skill routes that work there and covers what upstream
does not: models with no source asset, and the SwiftlyS2 side of delivering them.

Checked against SwiftlyS2 v1.5.0 and cs2-skills at commit `f92782f` (2026-10-20). Asset numbers come from CS2 builds
of 2026-11 and are build-scoped: re-extract a stock contract before relying on any of them.

## Decide the route

| Task | Go to |
| --- | --- |
| Port a CS:GO (Source 1) model, or a Source 2 model built for an older contract (AG1), as a player or agent model | Upstream [`cs2-player-model-porting`](https://github.com/AbsilDylan/cs2-skills/tree/main/cs2-player-model-porting). Classify the source first: [Phase 1](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-player-model-porting/references/source-classification-and-target-contract.md#phase-1-classify-the-source) |
| A weapon or item model with its own animations, new or ported: VNMClip and VNMGraph, first- and third-person graph roots | Upstream [`cs2-animgraph2-authoring`](https://github.com/AbsilDylan/cs2-skills/tree/main/cs2-animgraph2-authoring) |
| NPC gameplay: lifecycle, AI, navigation, combat | Upstream [`cs2-server-npc-runtime`](https://github.com/AbsilDylan/cs2-skills/tree/main/cs2-server-npc-runtime) |
| AG2 animation on a server-owned model entity | Upstream [`cs2-ag2-npc-runtime`](https://github.com/AbsilDylan/cs2-skills/tree/main/cs2-ag2-npc-runtime), with [modsharp-to-swiftlys2.md](references/modsharp-to-swiftlys2.md) for its ModSharp parts |
| Particles: a new or revised VPCF, schema lookup, control points, particle materials, validation | Upstream [`source2-particle-authoring`](https://github.com/AbsilDylan/cs2-skills/tree/main/source2-particle-authoring) and the `source2-particle-*` specialists it names |
| A prop, decoration, custom knife, custom grenade or pickup with no source asset | This skill: [the procedural route](#the-procedural-route) |
| Precache, spawn, swap or grant a model from a SwiftlyS2 plugin | [delivery-from-swiftlys2.md](references/delivery-from-swiftlys2.md). Precache basics are in SwiftlyS2-Skills' [`sws2-game-assets`](https://github.com/btnrv/SwiftlyS2-Skills/tree/main/skills/sws2-game-assets) |
| A compiled model that crashes, renders rotated or scaled, or is missing from the Workshop item | [compile-and-inspect.md](references/compile-and-inspect.md) |

Install every upstream skill you route to. Installing one skill does not fetch the skills it hands off to.

## The procedural route

Each worked example is the single source of truth for its outputs: edit the script, never the `.blend` it writes.

| Asset | Example | Route |
| --- | --- | --- |
| Map decoration | [`build_christmas_tree.py`](scripts/examples/map_decoration/build_christmas_tree.py), textures from [`make_textures.py`](scripts/examples/map_decoration/make_textures.py) | FBX, static, no skeleton |
| Knife on stock knife animations | [`build_example_butterfly.py`](scripts/examples/custom_knife/build_example_butterfly.py), map test harness [`give_example_butterfly.js`](scripts/examples/custom_knife/give_example_butterfly.js) | Hand-written SMD on the stock butterfly bones, DMX hull |
| Held grenade, its projectile and a pickup pile | [`build_easter_egg.py`](scripts/examples/grenade_projectile_pile/build_easter_egg.py) | SMD on the stock decoy frame, one-bone props, several hulls, Panorama icon |

All three import the shared [kit](scripts/source2_kit.py) and run headless:

```text
blender -b --factory-startup --python <example>.py -- --addon-root <CS2>/content/csgo_addons/<addon>
    --out <CS2>/content/csgo_addons/<addon>/rawmodels/<asset> [--render <preview folder>]
```

1. Extract the current stock contract the asset mirrors into a scratch folder outside every repository
   ([compile-and-inspect.md](references/compile-and-inspect.md#extract-a-stock-contract)). The frames measured so
   far are in [weapon-frames.md](references/weapon-frames.md).
2. Copy the closest example. Change geometry and constants; keep the kit's writers
   ([procedural-models.md](references/procedural-models.md)).
3. Run it with `--render`. Read the printed `STATS`, `BOUNDS`, `HITBOX`, `FIT` and `GATE` lines, then open every
   preview before compiling.
4. Compile into the matching game addon and compare the compiled model with the stock contract
   ([compile-and-inspect.md](references/compile-and-inspect.md)).
5. Check that every output sits under a folder the Workshop packer includes
   ([compile-and-inspect.md](references/compile-and-inspect.md#pack-for-the-workshop)).
6. Deliver it and check it in game ([delivery-from-swiftlys2.md](references/delivery-from-swiftlys2.md)). Static
   props and pickups: [props-and-pickups.md](references/props-and-pickups.md).

## Evidence labels

Use upstream's labels verbatim, from
[`cs2-animgraph2-authoring`](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/SKILL.md#non-negotiable-rules):

```text
static-observed -> source-authored / generated -> roundtrip-valid (optional)
-> compiled -> inspected -> packaged -> downloaded-vpk-inspected -> mounted
-> route-proven
-> first-person-validated / third-person-validated / gameplay-validated
-> in-game-validated
```

Report the highest label whose named evidence exists. Never infer a later label from an earlier one.

- `compiled` means resourcecompiler produced the output: syntax acceptance and nothing more.
- `inspected` means the compiled resource was read back and its semantics checked, for example with
  `model_facts.py` against the stock contract. Comparing timestamps or file sizes is not inspection.
- `in-game-validated` needs every applicable visual and gameplay branch, on clients.
- Not evidence of a working model: `FileExists` on the compiled path, or the model name the server reports. A knife
  the server reported as the custom model was drawn as the stock knife by every client (2026-11).

Where the examples stand:

| Example | Evidence |
| --- | --- |
| Christmas tree | Regenerates the meshes, VMDL, VMATs and textures of an original that is `in-game-validated` (2026-11). The FBX files differ from the original's only in the exporter's timestamp and embedded folder path |
| Example butterfly knife | `inspected`: compiled into two addons and read back (2026-11). Seen in game on 2026-11-12 on default-knife animations; the butterfly animations have only been seen on the stock knife model |
| Easter egg set | Regenerates an original that is `inspected` only. Never seen in game |

## Rules

1. Keep Valve-derived files out of every repository: VPK extracts, decompiled models, glTF exports and text dumps
   of stock resources. Use a scratch folder and delete it when done. Commit generators and original outputs only.
2. Compile from `content/csgo_addons/<addon>` into `game/csgo_addons/<addon>`. Never write loose files into
   `game/csgo`.
3. Re-extract the stock contract on the current build before relying on a number in these references.
4. Declare a `Skeleton` node in every SMD model, even a one-bone prop. Without it the root bone compiles rotated.
5. Never call `SetModel` on an entity before `DispatchSpawn`; pass the model as a spawn keyvalue. Apply only model
   paths precached for the current map.
6. Changing an installed CS2 file, such as the Workshop pack list in `gameinfo.gi` or the asset type registrations,
   needs the user's explicit approval and upstream's backup-and-diff procedure. A game update reverts it.
7. Before publishing a generated asset, record a redistribution basis for every input. A Blender FBX export embeds
   the absolute path of the folder it was built in.
8. Never patch the game's binaries or process memory to make an asset work.

## What an agent can do alone

Unattended, an agent can run the kit self-check and the generators, render previews, extract stock contracts,
compile, and run the inspect scripts. That reaches `inspected`.

Hand the rest to a person, as an explicit list:

- judging the previews for shape and shading problems the gates cannot catch;
- publishing the Workshop item, and any change to the installed `gameinfo.gi`;
- every in-game check on clients: first and third person, dropped and thrown states, hitbox and physics behaviour,
  a second observing client, each knife subclass route;
- deploying the plugin that delivers the asset.

## References

| Page | Use it for |
| --- | --- |
| [procedural-models.md](references/procedural-models.md) | The kit's arguments, writers and printed lines; units and axes per export route; materials; modelling techniques; build gates; known limitations |
| [weapon-frames.md](references/weapon-frames.md) | Where a stock contract lives in a compiled model; the single-bone and butterfly knife frames; the decoy frame; hitbox and hull rules |
| [props-and-pickups.md](references/props-and-pickups.md) | FBX decorations, textured round props, pickup piles, Panorama icons |
| [compile-and-inspect.md](references/compile-and-inspect.md) | Compiling, extracting stock contracts, the inspect scripts, Source2Viewer-CLI quirks, packing, and checking which copy a client loaded |
| [delivery-from-swiftlys2.md](references/delivery-from-swiftlys2.md) | Precache, props with a model, model changes, weapon spawns, custom knife grants, grenade model swaps, the map test harness |
| [modsharp-to-swiftlys2.md](references/modsharp-to-swiftlys2.md) | Upstream's ModSharp operations mapped to SwiftlyS2 v1.5.0, and what SwiftlyS2 exposes for AG2 controllers |
