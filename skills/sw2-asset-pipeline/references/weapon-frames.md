# Stock weapon frames

What a procedural model has to mirror to ride a stock weapon's animations: measured on CS2 builds of 2026-11 with
Source2Viewer-CLI 20.1. The numbers are build-scoped. Re-extract them before relying on one
([compile-and-inspect.md](compile-and-inspect.md#extract-a-stock-contract)).

Upstream describes the unified weapon model contract in
[cs2-animgraph2-authoring](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/authoring-and-compilation.md#3-model-contracts).
This page adds the measured frames and what the kit writes for them.

## Where the contract lives

| Fact | Source2Viewer-CLI | Field |
| --- | --- | --- |
| Bones, parents, rest transforms | `-b DATA` | `m_modelSkeleton`: `m_boneName`, `m_nParent`, `m_bonePosParent`, `m_boneRotParent` |
| Bones the mesh is skinned to | `-b DATA` | `m_remappingTable` |
| AnimGraph2 skeleton | `-b DATA`, `-b RERL` | `m_vecNmSkeletonRefs` |
| Holsters, unified flag, physics markup, inventory camera | `-b DATA` | `m_keyValueText`: `weapon_metadata`, `CPhysicsBodyGameMarkupData`, `prop_data`, `AttachmentCameraData` |
| Sequence names | `-b ASEQ` | `m_localSequenceNameArray` |
| Attachment positions | `-b MDAT` | `m_attachments`: `m_influenceNames`, `m_vInfluenceOffsets` |
| Attachment angles | `-b MDAT` as quaternions; `-d` as the Euler angles a VMDL takes | `m_vInfluenceRotations`; VMDL `relative_angles` |
| Hitboxes | `-b MDAT` | `m_hitboxsets` |
| Render bounds, draw calls | `-b MDAT` | `m_sceneObjects`: `m_vMinBounds`, `m_vMaxBounds`, vertex and index counts |
| Physics hulls, mass | `-b PHYS` | `m_parts`: `m_flMass`, hull `m_VertexPositions` as hex float32 in the parent bone's space |
| Surface properties | `-b RED2` | `surface_prop` |

`model_facts.py` prints all of these from one `-a` dump
([compile-and-inspect.md](compile-and-inspect.md#inspect-the-compiled-model)).

## What the kit writes for a weapon

`write_weapon_vmdl` mirrors the stock model's skeleton (identity rotations), attachments and holsters, and adds:

- `weapon_metadata` with `is_unified_model = true`, `prop_data` and `CPhysicsBodyGameMarkupData`, plus any extra
  game data the example passes (the held egg adds `ao_proxy_capsule`);
- an `NmSkeletonReference` to the stock `.vnmskel`. It compiles even where the Nm compiler registrations are
  missing, the state upstream's
  [Compiler Registration Recovery](https://github.com/AbsilDylan/cs2-skills/blob/main/cs2-animgraph2-authoring/references/authoring-and-compilation.md#7-compiler-registration-recovery)
  describes; compiling your own skeleton or clips needs them;
- bind-pose sequences named after the stock ones;
- one hull and one hitbox, both on `weapon_offset`.

## Knife on a single-bone frame

The bayonet (`weapon_knife_bayonet`, item definition index 500) moves no parts, so a custom knife on its frame is
one rigid mesh. A knife built on this frame was drawn in game on default-knife animations (2026-11-06).

| Bone | Parent | Parent-relative origin | Mesh |
| --- | --- | --- | --- |
| `weapon` | none | (0, 0, 0.5) | |
| `weapon_offset` | `weapon` | (0, 0, 0) | all of it (`m_remappingTable` [1, 1]) |
| `ag1_hand_r` | `weapon_offset` | (0, 0, 0.5) | |

| Item | Stock value |
| --- | --- |
| Rotations | identity |
| NmSkeleton | `animation/skeletons/weapons/knife_bayonet.vnmskel` |
| Holsters | `knife` preferred, `knife` fallback |
| Sequences | `refPose`, `inventory_inspect`, `inventory_icon` |
| Attachments | `weapon_holster_center` (0, 0, 1.518), `camera_inventory`, `stattrak`, `nametag`, all on `weapon_offset` |
| Render bounds | x −1.85…1.26, y −0.64…0.66, z −3.67…10.84 |
| Shape | Long axis +Z, centre line x ≈ −0.07. Grip z −2.2…1.54, pommel to −3.67, crossguard 1.54…1.74, blade to 10.84 and flat in Y. The edge faces +X, which points down in a forward grip |
| Hitbox | on `weapon_offset`, surface `weapon`: the render bounds with z − 0.5 |
| Physics | one hull on `weapon_offset`, surface `WeaponKnife`, mass 3.0 |

Keep the grip radius near 0.5: a thicker or thinner grip makes the first-person fingers clip or float.

## Knife on the butterfly frame

The butterfly knife (`weapon_knife_butterfly`, item definition index 515) has moving bones. The stock mesh is
skinned to `weapon_offset`, `blade`, `rear` and `lock` (`m_remappingTable` [1, 3, 4, 5, 1]); `front` carries
nothing. All rest rotations are identity; the example's `BONES` holds the exact origins.

| Bone | Parent | Parent-relative origin | Carries |
| --- | --- | --- | --- |
| `weapon` | none | (0, 0, 0.5) | |
| `weapon_offset` | `weapon` | (0, 0, 0) | front handle |
| `front` | `weapon_offset` | (−0.173, 0, 1.520) | nothing |
| `blade` | `front` | (0.036, −0.022, 0.009) | blade |
| `rear` | `blade` | (0.669, 0.022, 0.409) | rear handle |
| `lock` | `rear` | (0.929, −0.022, −6.213) | latch |
| `ag1_hand_r` | `weapon_offset` | (0, 0, 0.5) | |

The moving bones all turn about +Y, and the blade lies flat in XZ. In model space, the sums of the origins, the
blade turns about a pin in the front handle at (−0.137, −0.022, 2.029), the rear handle about a pin in the blade at
(0.532, 0, 2.439), and the latch about a pin in the rear butt at (1.461, −0.022, −3.775). The example prints these as
`PIVOTS`.

Bone angles at stock clip frames, decoded from the clips' compressed pose data, in degrees about +Y:

| Pose | Clip frame | `blade` | `rear` | `lock` |
| --- | --- | --- | --- | --- |
| idle | `idle1` | 0 | 0 | 43.3 |
| closed | `draw`, frame 0 | 169.8 | −171.4 | 39.0 |
| flip | `draw`, frame 12 | −155.0 | −88.3 | 39.0 |
| fan | `lookat01`, frame 6 | −73.7 | −70.5 | −104.7 |
| shut (fit check only) | | 180 | −180 | 39 |

The bind pose is open. Closing turns the blade about 180° and the rear about −180°, which carries the rear handle
to the other side of the front one. A solid handle would cut through the blade, so each handle is a pair of side
plates (|y| 0.16…0.38) that the blade (|y| ≤ 0.065) and latch (|y| ≤ 0.07) pass between, and the blade outline is
sized to where the closed handles lie. The `FIT` lines count intersecting triangle pairs for every pose above,
ignoring each pin inside the part it carries.

`stattrak` sits on `blade` and `nametag` on `rear`; `weapon_holster_center` (0, 0, 1.518) and `camera_inventory`
sit on `weapon_offset`. An inventory-skin plugin's StatTrak counter or name tag would attach to these.

Compiled example against the stock model (2026-11-12):

| Field | Stock | Example |
| --- | --- | --- |
| Bones | 7, as above | identical |
| `m_remappingTable` | [1, 3, 4, 5, 1] | [0, 1, 2, 3, 4, 5, 6, 1]: the SMD lists every bone |
| NmSkeleton | `knife_butterfly.vnmskel` | same reference |
| Sequences | `refPose`, `inventory_inspect`, `inventory_icon` | `refPose` |
| Game data | `AttachmentCameraData`, `CPhysicsBodyGameMarkupData`, `prop_data`, `weapon_metadata` | the same without `AttachmentCameraData` |
| Hull | one on `weapon_offset`, `WeaponKnife`, mass 3.0 | one on `weapon_offset`, `weaponknife` (same hash), mass 0.0 |
| Hitbox | `weapon_offset`, surface `weapon` | `weapon_offset`, surface `weapon`, [−0.437, −0.415, −5.438]…[1.636, 0.415, 7.329] |
| Draw calls | 1 material | 3 materials |

The butterfly animations that move these bones play only after `ChangeSubclass 515`. With the item definition index
left at the default knife, clients then drew the stock knife (2026-11-12); setting the index too is the plugin route
in [delivery-from-swiftlys2.md](delivery-from-swiftlys2.md#give-a-player-a-custom-knife), not yet seen in game with
515.

## Grenade on the decoy frame

The held model mirrors `weapon_decoy`. These values were checked against the stock model on a 2026-11 build and are
what the egg example ships; the egg set itself is `inspected` only.

| Bone | Parent | Parent-relative origin |
| --- | --- | --- |
| `weapon` | none | (0, 0, 0) |
| `weapon_offset` | `weapon` | (0, 0, 0) |
| `handle` | `weapon_offset` | (0.276, 0.371, 2.867) |
| `pin` | `weapon_offset` | (0.111, −0.595, 2.607) |
| `ring` | `pin` | (−0.539, 0, 0) |
| `ag1_hand_r` | `weapon_offset` | (0, 0, 0) |

| Item | Value |
| --- | --- |
| Rotations | identity |
| NmSkeleton | `animation/skeletons/weapons/decoy.vnmskel` |
| Holsters | `grenade0` preferred, `grenade1` fallback |
| Attachments | `weapon_holster_center` (0, 0, 0), `camera_inventory`, `decoy_particle` (0, 0, 2.007), all on `weapon_offset` |
| Hull surface | `weaponflashbang` |
| Grip | The first-person hand wraps the can: hexagonal caps of radius 1.0 at z −2.50…−1.54 and 1.03…1.97, a waist of radius 0.735, centre z −0.263. A wider held model buries the fingers |
| Pin, ring, spoon | Parts of the one stock mesh skinned to `pin`, `ring` and `handle`, which the stock `thrown` sequence scales to 0.0001. A mesh skinned entirely to `weapon_offset` has nothing to hide |
| Thrown scale | Stock `dropped` and `thrown` sequences scale `weapon_offset` (decoy 1.5×, HE 1.3×) and the stock hulls are scaled to match. A bind-pose model needs neither: size the projectile as it should fly and keep hulls 1:1 |
| HE reference | The HE frag body fits a sphere of radius 1.634; the egg is sized against it |

The projectile is a separate one-bone prop. The example gives it a `decoy_particle` attachment and a `thrown`
sequence, mirroring the stock decoy model, and makes it 1.3 times the held size, the HE ratio.

## Hitbox and hull rules

- Hitbox bounds are in the parent bone's space. On the knife frames `weapon_offset` sits at z 0.5, so the hitbox is
  the model-space bounds with z − 0.5; the stock bayonet's hitbox is its render bounds shifted that way. On the
  decoy frame `weapon_offset` is at the origin and the two spaces agree.
- Write hulls as unskinned KV2 DMX in model space and bind them with `parent_bone` in the VMDL. An SMD hull
  compiles rotated +90° about Z, while the render SMD does not. Source2Viewer-CLI decompiles hulls in bone space;
  do not copy that frame back.
- Build a hull from a few dozen support points with `maxHullVertices 0` and `faceMergeAngle 0`. Re-fitting a dense
  hull to a 32-vertex budget overshot a knife tip by 2.6 inches; 40 support points compiled to 46 vertices, at most
  0.14 outside. The butterfly example's hull, from 40 directions, compiled to 39 vertices.
- The compiler still moves authored hull vertices: up to 4.5 inches on a pile and 0.42 on a held model. Measure
  with `hull_report.py` after every compile.
