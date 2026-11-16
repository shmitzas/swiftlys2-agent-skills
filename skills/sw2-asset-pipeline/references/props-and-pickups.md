# Props and pickups

Reference for static models: a decoration exported as FBX, textured round props, pickup piles, and the Panorama icon a
pickup can carry. Measured on CS2 builds of 2026-11. The tree is `in-game-validated`; the egg set is `inspected`
only. Spawning them from a plugin is in
[delivery-from-swiftlys2.md](delivery-from-swiftlys2.md#spawn-a-prop-with-a-model).

## FBX decoration

[`build_christmas_tree.py`](../scripts/examples/map_decoration/build_christmas_tree.py) builds in metres and exports
two FBX files, the render mesh and a hull, with the settings below.

| Setting | Value |
| --- | --- |
| Export | `apply_unit_scale=True`, `apply_scale_options="FBX_SCALE_NONE"`, `global_scale=1.0`, `axis_forward="-Z"`, `axis_up="Y"`, `mesh_smooth_type="OFF"`, `use_tspace=False`, `add_leaf_bones=False`, `bake_anim=False`, `path_mode="STRIP"`, `embed_textures=False` |
| `import_scale` | `0.393701` on the render mesh and on the hull |
| Facing | Geometry is designed facing +X and baked facing Blender's front (−Y), which ModelDoc maps to Source +X, so the star faces the model's forward axis |
| Skeleton | None. The compiled model has no bones and keeps its axes; the root-rotation trap is specific to SMD input |
| Hull | One convex hull through the presents' corners, a ring at the base and the tree top; surface `wood`, no parent bone, `faceMergeAngle 10` |
| Materials | 12 VMATs written from the same table as the Blender materials, each remapped explicitly |

Compiled check: render bounds reach z = 110.93 for a top at about 2.82 m, and the hull compiled to 26 vertices.

Before publishing the FBX files themselves, note that the exporter writes the absolute path of the build folder into
them despite `path_mode="STRIP"`.

## Textured round props

[`build_easter_egg.py`](../scripts/examples/grenade_projectile_pile/build_easter_egg.py) paints its textures in numpy
and maps them with revolution UVs.

- SMD UVs are Blender's: v = 1 is the top row of the PNG. A glTF export of the compiled egg confirmed it (glTF
  v = 0 at the SMD v = 1 pole); `uv_check.py` prints both. The convention decides which end a pattern lands on and
  which atlas tile a mesh reads.
- Revolution UVs run u around the axis and v along the arc. Repeat every pattern a whole number of times around so
  the u seam hides, and keep both poles plain, because u pinches there.
- Size features in surface units, not UV units: the egg's dots are round on the egg because each is measured against
  the circumference at its own height.
- Take a stroke's slope at its band's own height, not per row. Near a pole the circumference reaches 0 and a per-row
  slope floods the pole with the stroke.
- Match texel aspect to the surface: the egg is about 2.3 times as far around as it is long, so its texture is 2:1.

## Pickup piles

| Rule | Example value |
| --- | --- |
| Atlas the pile's variants as tiles stacked in v, so the u seam wraps inside one tile | six egg designs in a 512 × 2048 atlas |
| Leave a gutter painted in the pole colour around every tile and map each mesh inside it, so mip bleed between tiles stays invisible | 6 px gutter (`atlas_tile`) |
| Make pile items bigger than the held item so they read from across a room | pile eggs 1.6 times the held egg |
| Give each physical part its own `PhysicsHullFile` and surface prop | nest `foliage`, eggs `fruit` |
| Settle items by dropping them onto what is already placed | `build_pile`: 18 eggs on a straw nest |

The floor needs a check after every compile. On one pile, hulls whose widest part sat above the floor compiled
anywhere from 0.28 inches below it to 0.22 above; a pile whose floor face was its widest part compiled flush. Run
`hull_report.py --floor 0` ([compile-and-inspect.md](compile-and-inspect.md#inspect-the-compiled-model)); the egg
nest compiled with its lowest hull vertex at z 0.001.

## Panorama icons

The egg example writes a killfeed icon to `panorama/images/icons/equipment/easter_egg.svg`, compiled to `.vsvg_c`.

- resourcecompiler wraps the SVG bytes without parsing them: a decompiled `.vsvg_c` returns the source byte for byte.
  A clean compile says nothing about whether Panorama draws the icon.
- The example's writer allows only the path commands `M`, `C` and `Z` and refuses anything else, draws detail as
  even-odd cut-outs kept inside the silhouette, and always sets the root `width` and `height` (32), which set the
  raster size.
- `panorama/images/icons/equipment` is outside the stock Workshop pack list
  ([compile-and-inspect.md](compile-and-inspect.md#pack-for-the-workshop)).
- How the icon reaches the killfeed is in
  [delivery-from-swiftlys2.md](delivery-from-swiftlys2.md#swap-a-grenades-models). None of it has been seen in game.
