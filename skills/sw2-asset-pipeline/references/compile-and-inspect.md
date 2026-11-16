# Compile, inspect and pack

How to turn generated sources into compiled models, check them against the stock contract, and get them into the
Workshop item players download. Tool behaviour here was recorded in 2026-11 with Source2Viewer-CLI 20.1.7467. For
Source2Viewer-CLI options and general recipes, see SwiftlyS2-Skills'
[Source2Viewer reference](https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-game-assets/references/source2viewer.md).

## Before you start

- `resourcecompiler.exe` from the CS2 Workshop Tools, in `<CS2>/game/bin/win64/`.
- Source2Viewer-CLI 20.1 or newer. Release 20.0.6980 fails on models the current compiler writes: on a model
  compiled on 2026-11-12 it threw `UnexpectedMagicException: Unknown KVType for variable 'datatype': 26 (0x1A)` and
  still exited with code 0. Read the output for exceptions; the exit code proves nothing.
- Python 3.10 or newer. `hull_report.py`, `measure_gltf.py` and `uv_check.py` also need numpy. Script paths below
  are relative to this skill's folder.
- A scratch folder outside every repository for stock extracts and dumps. Delete it when done.

## Compile

1. Run the generator, which writes the sources into the content addon.
2. Compile each VMDL:

   ```powershell
   & "<CS2>\game\bin\win64\resourcecompiler.exe" -f -i "<CS2>\content\csgo_addons\<addon>\<path>.vmdl"
   ```

   The compiler derives the output from the input path: the same relative path under
   `<CS2>/game/csgo_addons/<addon>/`. `-f` force-compiles every resource the model pulls in, so its materials and
   textures are rebuilt with it.
3. Read the compiler output for errors and warnings. A clean run makes the model `compiled` and nothing more.
   Upstream's full build order, for projects with graphs and clips, is in
   [Compilation](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/authoring-and-compilation.md#6-compilation).

## Extract a stock contract

1. Find the compiled path in the game's VPK:

   ```text
   Source2Viewer-CLI -i "<CS2>/game/csgo/pak01_dir.vpk" -l -e vmdl_c -f weapons/models/knife/
   ```

2. Extract the one file. When the filter matches a single file, `-o` names the output file:

   ```text
   Source2Viewer-CLI -i "<CS2>/game/csgo/pak01_dir.vpk" -f weapons/models/knife/knife_butterfly/weapon_knife_butterfly.vmdl_c -o <scratch>/stock.vmdl_c
   ```

3. Dump every block and read the contract out of it:

   ```text
   Source2Viewer-CLI -i <scratch>/stock.vmdl_c -a > <scratch>/stock.txt
   python -B scripts/inspect/model_facts.py <scratch>/stock.txt
   ```

4. For attachment angles in the Euler form a VMDL takes, decompile with `-d -o <scratch>/stock.vmdl`, which also
   writes the mesh, hull and sequence DMX files beside it. The `-a` dump carries the angles as quaternions.
5. For per-bone mesh extents, export glTF and measure it. glTF export needs `-d`; joint indices follow the `-b DATA`
   bone order, which `model_facts.py` prints:

   ```text
   Source2Viewer-CLI -i <scratch>/stock.vmdl_c -d --gltf_export_format gltf -o <scratch>/stock.gltf
   python -B scripts/inspect/measure_gltf.py <scratch>/stock.gltf --bones weapon,weapon_offset,front,blade,rear,lock,ag1_hand_r
   ```

6. Record the CLI version with the dump. Upstream's rule applies: a cache written by another release is a different
   reference, not a refresh
   ([Decompiler versions](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/authoring-and-compilation.md#decompiler-versions-and-the-dmx-frame)).

[weapon-frames.md](weapon-frames.md#where-the-contract-lives) lists which block holds which fact.

## Inspect the compiled model

1. Dump the compiled model the same way:
   `Source2Viewer-CLI -i <CS2>/game/csgo_addons/<addon>/<path>.vmdl_c -a > <scratch>/ours.txt`. `model_facts.py` and
   `hull_report.py` read both UTF-16, which Windows PowerShell's `>` writes, and UTF-8.
2. Compare it with the stock dump:
   `python -B scripts/inspect/model_facts.py <scratch>/ours.txt <scratch>/stock.txt`. Check bones and rest
   rotations, the remapping table, the NmSkeleton reference, game data, sequences, attachments, hitbox, hull bone,
   surface and mass, and the render bounds against the generator's `BOUNDS` line. A root rotation of
   [0, 0, 0.7071, 0.7071] instead of [0, 0, 0, 1] means the VMDL has no `Skeleton` node.
3. Check every hull with `hull_report.py`, listing the hull DMX files in the compiled order. That order need not match
   the VMDL: the egg pile's two hulls compiled in reverse. If every re-fit distance looks implausible, swap the files.
4. Check UVs and per-bone extents from a glTF export of the compiled model with `uv_check.py` and `measure_gltf.py`.
5. Check dependencies with `-b RERL`: every listed resource has to be in the addon or in the base game.

| Script | Reads | Reports |
| --- | --- | --- |
| [`model_facts.py`](../scripts/inspect/model_facts.py) | `-a` dumps | Bones and rest transforms, remapping table, NmSkeleton and resource references, game data, sequences, attachments, hitboxes, physics hulls and mass, render bounds, draw calls, surface props |
| [`hull_report.py`](../scripts/inspect/hull_report.py) | `-a` dump, hull DMX files, `--floor` | Vertex counts in and out, how far the compiler moved the authored points, reach past the render bounds, vertices below the floor |
| [`measure_gltf.py`](../scripts/inspect/measure_gltf.py) | glTF export, `--bones` | Bounds per skinned bone in Source inches; glTF (x, y, z) is Source (y, z, x) × 0.0254 |
| [`uv_check.py`](../scripts/inspect/uv_check.py) | glTF export, `--tiles` | v at each draw call's top and bottom vertex (glTF v = 1 − SMD v); with `--tiles`, where each atlas tile's vertices sit |
| [`particle_refs.py`](../scripts/inspect/particle_refs.py) | the CLI, the VPK, a `-l` listing, particle paths | A stock particle's child particles, materials and models, flagging any the live VPK lacks |
| [`soundevent_summary.py`](../scripts/inspect/soundevent_summary.py) | decompiled `soundevents/`, a `-l` listing, `file::event` queries | Type, sound files, position offset and child events, flagging sound files the live VPK lacks |

Each script's docstring (`--help`) gives its exact command lines. Particle authoring itself belongs to upstream's
`source2-particle-*` skills.

A model compiled for an older CS2 build can pass `FileExists` and still crash the server inside
`SkeletonInstance::SetupModel` (seen in production in 2026). Before adding a third-party model to a pool a plugin picks
from, dump it with a current CLI, compare it with a stock model of the same kind, and load it on a disposable server.

## Pack for the Workshop

Workshop Tools pack only the folders listed under `AddonConfig` > `VpkDirectories` in `<CS2>/game/csgo/gameinfo.gi`
([upstream: packer roots](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/workshop-runtime-and-debugging.md#2-packer-roots-and-gameinfo)).

1. Compare your output paths with the list. On build 2000943 (2026-11-11) the stock file includes `maps` (except
   `maps/content_examples`), `cfg/maps`, `materials`, `models`, `panorama/images/overheadmaps`,
   `panorama/images/map_icons`, `panorama/images/custom_game`, `panorama/layout/custom_game`,
   `panorama/styles/custom_game`, `particles`, `resource/overviews`, `scripts`, `sounds`, `soundevents`,
   `lighting/postprocessing`, `postprocess` and `addoninfo.txt`
   ([GameTracking-CS2 copy](https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/game/csgo/gameinfo.gi#L534-L556)).
2. These examples write outside that list: everything under `weapons/` (the knife and held grenade models, and the
   knife's materials) and `panorama/images/icons/equipment/` (the egg's killfeed icon). For the models and
   materials, change the example's path constants to a packed folder or add `weapons` to the list. The killfeed icon
   has to stay in `panorama/images/icons/equipment/`, where the killfeed looks it up by weapon name
   ([delivery-from-swiftlys2.md](delivery-from-swiftlys2.md#swap-a-grenades-models)), so for it only adding that
   folder to the list works, as step 3 describes.
3. Adding folders edits an installed CS2 file. Get the user's approval first and follow upstream's procedure: hash and
   back up the file, add only the missing lines, report the diff, restore afterwards, and restart Workshop Tools so it
   rereads the list. A game update rewrites the file (seen 2026-11), so check the list again before every publish.
4. After publishing, inspect the downloaded VPK's file list as upstream describes in
   [VPK Inspection](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/workshop-runtime-and-debugging.md#3-vpk-inspection).

## Check which copy a client loaded

A mounted Workshop addon is searched before loose files in `game/csgo` and `game/csgo_addons/<addon>`. This was seen
in 2026-09 with Panorama files on a listen server that mounted the published addon: edits to files the published
addon already contained had no effect, while new files loaded. A stale published copy makes a real fix look like a
no-op.

1. Suspect it when an error you fixed keeps appearing, or when new files work and edited files do not.
2. Put an unmistakable marker into the asset, for example a magenta colour on one material, rebuild, and look. If the
   marker does not show, the client is not loading your file.
3. Stop mounting the published addon while you iterate, or republish it.
