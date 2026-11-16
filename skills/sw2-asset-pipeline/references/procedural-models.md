# Procedural models: the kit and its conventions

Reference for [`source2_kit.py`](../scripts/source2_kit.py) and the examples built on it. Everything here was run
on Blender 5.2 against CS2 builds of 2026-11; other Blender versions are untested.

## Scripts

| File | Contents |
| --- | --- |
| [`source2_kit.py`](../scripts/source2_kit.py) | Shared Blender kit: arguments, scene, SMD, hull DMX, VMDL and VMAT writers, previews, self-check |
| [`build_christmas_tree.py`](../scripts/examples/map_decoration/build_christmas_tree.py) | FBX decoration: fir tree, baubles, fairy lights, star, presents, one convex hull |
| [`make_textures.py`](../scripts/examples/map_decoration/make_textures.py) | The tree's textures. Runs in a system Python 3.10+ with Pillow and numpy, because Blender's Python has no Pillow |
| [`build_example_butterfly.py`](../scripts/examples/custom_knife/build_example_butterfly.py) | Knife on the stock butterfly frame, its parts skinned to the moving bones |
| [`give_example_butterfly.js`](../scripts/examples/custom_knife/give_example_butterfly.js) | Map `point_script` harness that gives every player the knife |
| [`build_easter_egg.py`](../scripts/examples/grenade_projectile_pile/build_easter_egg.py) | Held model on the decoy frame, projectile, pickup pile, killfeed icon |
| `inspect/*.py` | Source2Viewer-CLI readers, see [compile-and-inspect.md](compile-and-inspect.md#inspect-the-compiled-model) |

## Arguments

```text
blender -b --factory-startup --python <example>.py -- --addon-root <addon> --out <folder> [--render <folder>]
```

| Argument | Meaning |
| --- | --- |
| `--addon-root` | The content addon, `<CS2>/content/csgo_addons/<addon>`. VMDLs, VMATs, textures and icons are written to their addon-relative paths under it |
| `--out` | Folder for the meshes, hulls and `.blend`. Must be inside `--addon-root`, because the VMDLs reference the meshes addon-relative |
| `--render` | Also render Cycles previews (CPU, denoised) into this folder |
| `--only` | Easter egg only: comma-separated preview shots to render |

`make_textures.py` takes `--addon-root` only. Run it before the tree builder, whose `.blend` loads its PNGs.

The kit checks itself without an example: `blender -b --factory-startup --python scripts/source2_kit.py` prints
`source2_kit self-check ok`. The examples set `sys.dont_write_bytecode`, so they leave no `__pycache__` in the skill.

## Printed lines

| Line | Example | Meaning |
| --- | --- | --- |
| `STATS` | all | Triangles per part or model, hull vertex counts |
| `BOUNDS` | all | Model-space bounds: inches for the SMD examples, metres for the tree |
| `HITBOX` | knife, egg | The hitbox written into the VMDL, in `weapon_offset` space |
| `PIVOTS` | knife | Model-space pivots of the blade, rear handle and latch |
| `FIT <pose>` | knife | Intersecting triangle pairs between parts on different bones at a stock pose; `clear` means none |
| `WARNING <part> non_manifold_edges=` | knife | A closed part has open edges |
| `GATE ok` / `GATE FAILED` | egg | Every part has positive signed volume and no non-manifold edges; a failure stops the run |
| `AO`, `SIZE`, `PILE` | egg | AO proxy capsule, sizes against the HE grenade, pile footprint and height |
| `RENDERED` | all | A preview was written |

## Kit functions

| Function | Writes or does |
| --- | --- |
| `cli(doc, *extra)` | Parses the arguments above; adds `out_rel`, the `--out` folder relative to the addon |
| `clear_scene(scale_length)` | Empties the factory scene. `0.0254` makes one Blender unit one inch, which is one Source unit |
| `write_smd(path, bones, skin_bone, parts)` | Text SMD. `bones`: `(name, parent index or -1, parent-relative origin)` with identity rotations. `parts`: `(object, material)` weighted 100 % to `skin_bone`, or `(object, material, bone index)` per part for a rig whose parts move separately. Vertices stay in model space; counter-clockwise triangles face out |
| `support_points(objects, count)` | The extreme vertex along each of `count` Fibonacci-sphere directions: hull input |
| `convex_hull(points)` | BMesh holding only the convex hull |
| `write_hull_dmx(path, model_name, points, mtl)` | Unskinned model-space KV2 DMX hull. Element ids derive from `model_name`, so reruns are byte-identical |
| `write_vmdl(path, children)` | ModelDoc file in ModelDoc's own KV3 layout |
| `material_group(remaps)` | `DefaultMaterialGroup` remapping each mesh material to a VMAT |
| `render_mesh(filename, scale, name)` | `RenderMeshFile` with its `import_scale` |
| `hulls(files, parent, scale, merge_angle)` | One `PhysicsHullFile` per `(name, mesh, surface prop)`; `maxHullVertices 0` keeps every authored vertex |
| `skeleton(bones)` | `Skeleton` node from the `write_smd` bone list |
| `attachment(...)`, `animations(*names)` | Attachments; `AnimBindPose` sequences |
| `write_weapon_vmdl(...)` | Unified weapon model mirroring a stock one: skeleton, attachments, bind-pose sequences, `NmSkeletonReference`, `prop_data`, `weapon_metadata`, `CPhysicsBodyGameMarkupData`, extra game data, one hull and one hitbox on `weapon_offset` |
| `write_vmat(path, color, rough, metal, ...)` | `csgo_complex` material, optionally alpha-tested, self-illuminated or normal-mapped |
| `write_png(path, rgb)` | 8-bit RGB PNG from an array, without Pillow |
| `setup_render`, `look_at`, `blender_material`, `mesh_from`, `bounds` | Preview and mesh helpers |

## Units and axes per export route

| Route | Blender scene | ModelDoc reads | Axes | `import_scale` |
| --- | --- | --- | --- | --- |
| Hand-written SMD and KV2 DMX (the kit) | 1 unit = 1 inch | Values as Source inches | As written: author in Source model space, +X forward, +Z up | `1.0` |
| FBX from a metre scene, `apply_unit_scale=True`, `apply_scale_options="FBX_SCALE_NONE"`, `axis_forward="-Z"`, `axis_up="Y"` | Metres | 1 FBX centimetre as 1 unit | Source (x, y, z) = (−Blender y, Blender x, Blender z): Blender's front (−Y) becomes Source forward (+X) | `0.393701` |

- The factor follows the exporter, not ModelDoc; other FBX setups need other factors. After the first compile,
  compare the compiled render bounds with the generator's `BOUNDS` line. The tree's top at about 2.82 m compiles to
  z = 110.93.
- Prefer the SMD and DMX route whenever a stock skeleton applies. Nothing is converted, and the stock bones keep
  their exact identity rest rotations. Blender's armature exporters re-axis bones instead.
- The SMD route needs a `Skeleton` node in the VMDL even for a one-bone prop (`skeleton()` writes it). Without one,
  the root bone compiles rotated +90° about Z: render X and Y swap while a DMX hull keeps its frame.

## Materials

Remap every mesh material explicitly (`material_group`): `from = "<mesh material>.vmat"`, `to = "<VMAT path>"`.
With remaps, the FBX exporter's `path_mode="STRIP"` is harmless, and `GetFbxMaterialPath Failed!` in the compile log
is only the lookup before the remap.

| `csgo_complex` keys | Use | In |
| --- | --- | --- |
| `TextureColor` | Colour texture; a constant is written `"[r g b a]"` | all |
| `g_flMetalness`, `TextureRoughness` | Metalness; roughness as a constant | all |
| `F_ALPHA_TEST`, `g_flAlphaTestReference`, `TextureTranslucency` | Alpha-tested cards; the alpha comes from `TextureTranslucency` | tree needles |
| `F_SELF_ILLUM`, `g_flSelfIllumBrightness`, `g_vSelfIllumTint`, `g_flSelfIllumAlbedoFactor`, `TextureSelfIllumMask` | Glowing bulbs, unmasked | tree lights and star |
| `TextureNormal` | Normal map; the kit's default is `materials/default/default_normal.tga` | tree needles |

- Normal maps: the tree's needle material uses a generated normal map, written in the OpenGL convention (green
  = +V), and the tree is `in-game-validated`. Whether CS2 expects that green convention has not been checked
  separately, so the knife and the eggs model their relief as geometry.
- Foliage: alpha-tested cards whose custom split normals point out of the crown (`normals_split_custom_set`) shade
  as one volume. They survive FBX export with `mesh_smooth_type="OFF"`. The cards carry both faces in the mesh, so the
  material needs no back-face rendering, and an opaque inner cone keeps the crown from reading as see-through.

## Modelling techniques that held up

| Technique | How | Watch for |
| --- | --- | --- |
| Surfaces of revolution | Catmull-Rom (radius, height) profile resampled at equal arc length; run it counter-clockwise in (r, z) so faces wind outward; r = 0 at an end becomes a pole | Space rings by arc length so domes keep their detail |
| Relief as geometry | numpy displacement on the (height, angle) grid before meshing | Features narrower than 2 segment spacings, or wavelengths shorter than 5 grid cells, render faceted |
| Flat parts with holes | Outline and hole loops extruded between two planes with chamfered edges (`prism` in the knife) | Wind the outline counter-clockwise and holes clockwise |
| Blobs (not in the shipped examples) | Metaball ellipsoids, `bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph))`, then a voxel remesh at adaptivity 0 before displacing | The raw polygonizer leaves slivers whose vertex normals render as pits. A metaball's visible extent is not radius × size: read the bounds after conversion |
| Resting objects on objects | Lower each object until it touches what is already placed, allowing a small interpenetration so contacts show no gap (`build_pile` in the egg) | Drop order decides the heap |
| Reading side-on | First person sees a knife from the side: anything meant to read as two lobes must be staggered along the blade, not only side by side | |

API notes: `mesh.corner_normals` replaced loop normals in Blender 4.1 (`corner_normal()` handles both), and in 5.x
`Material.node_tree` already exists, so the kit only sets `use_nodes` when it is missing.

## Build gates

| Gate | Where | Catches |
| --- | --- | --- |
| Positive signed volume and zero non-manifold edges per closed part | `gate()` in the egg; `finish()` warns in the knife | Inverted or open parts, which shade and collide wrongly |
| Bounds and hitbox against the stock frame | `BOUNDS` and `HITBOX` lines | Wrong units or axes, before compiling |
| Part overlaps at stock poses | `FIT` lines in the knife | Moving parts that cut through each other during the stock animations |
| Cycles previews from fixed cameras, close-ups included, opened and looked at | `--render` | Surface defects: a pitted surface looked fine in the full-length shot |

## Determinism

Seeds are fixed and hull element ids derive from the model name, so a second run gives byte-identical output for
every file except the `.blend` and the `.fbx` (49 of 49 files in a 2026-11 check). The FBX exporter writes a
timestamp and the folder path.

## Known limitations

- `write_weapon_vmdl` sets no physics mass. Kit-built weapons compile with mass 0.0 where the stock knives have 3.0.
  The effect in game has not been checked.
- The kit writes `AnimBindPose` sequences named after the stock ones (`refPose`; `hudmodel`, `dropped` and `thrown`
  on the decoy frame) where upstream's
  [unified model contract](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/authoring-and-compilation.md#owner-object-model)
  uses `AnimIncludeModel`. It writes no `AttachmentCameraData` and no `inventory_icon` or `inventory_inspect`
  sequences, which the stock knives carry. The effect on inventory views has not been checked.
- Blender's FBX exporter embeds absolute texture paths even with `path_mode="STRIP"`. Publishing a generated FBX
  publishes the folder it was built in.
