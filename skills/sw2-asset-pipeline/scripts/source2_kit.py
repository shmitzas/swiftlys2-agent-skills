"""Blender-side kit for procedural CS2 models: hand-written SMD meshes, KV2 DMX hulls, ModelDoc VMDLs and
csgo_complex VMATs, plus the scene, argument and preview plumbing the examples share.

An example imports it and runs as  blender -b --factory-startup --python <example> -- --addon-root <addon> --out <dir>
SMD and DMX values are Source model space in inches (scene scale_length 0.0254: 1 Blender unit = 1 inch), written as
text so stock rest transforms survive bit-exact.
Self-check:  blender -b --factory-startup --python source2_kit.py
"""
import argparse
import itertools
import math
import os
import struct
import sys
import uuid
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Vector


# ---------------------------------------------------------------- arguments and scene

def cli(doc, *extra):
    """Arguments after Blender's `--`. extra: (flag, help) pairs for options only one example has."""
    p = argparse.ArgumentParser(prog="blender -b --factory-startup --python <script> --", description=doc,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--addon-root", required=True, help="content addon to write materials, icons and VMDLs into, "
                                                       "e.g. <CS2>/content/csgo_addons/<addon>")
    p.add_argument("--out", required=True, help="folder for the meshes and the .blend, inside --addon-root")
    p.add_argument("--render", metavar="DIR", help="also render Cycles previews into DIR")
    for flag, text in extra:
        p.add_argument(flag, help=text)
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    a.addon_root, a.out = os.path.abspath(a.addon_root), os.path.abspath(a.out)
    try:
        rel = os.path.relpath(a.out, a.addon_root)
    except ValueError:  # another drive
        rel = ".."
    if rel == ".." or rel.startswith(".." + os.sep):
        p.error("--out must be inside --addon-root: the VMDLs reference the meshes addon-relative")
    a.out_rel = "" if rel == "." else rel.replace(os.sep, "/") + "/"
    os.makedirs(a.out, exist_ok=True)
    return a


def clear_scene(scale_length=1.0):
    """Empty the factory scene. scale_length 0.0254 makes a Blender unit one inch, i.e. one Source unit."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = scale_length
    return sc


def save_blend(path):
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 next to the outputs
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()


def setup_render(world_rgb, samples, resolution):
    """Plain dark world and denoised CPU Cycles for the preview shots."""
    sc = bpy.context.scene
    world = bpy.data.worlds.new("preview_world")
    wnt = node_tree(world)
    bg = next((n for n in wnt.nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        bg = wnt.nodes.new("ShaderNodeBackground")
        out = next((n for n in wnt.nodes if n.type == "OUTPUT_WORLD"), None) or wnt.nodes.new("ShaderNodeOutputWorld")
        wnt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    bg.inputs[0].default_value = (*world_rgb, 1.0)
    sc.world = world
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = resolution
    return sc


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------- materials and objects

def node_tree(idblock):
    if idblock.node_tree is None:  # 5.x creates it already; the setter is deprecated
        idblock.use_nodes = True
    return idblock.node_tree


def principled(m):
    nt = node_tree(m)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return nt, bsdf


def blender_material(name, png=None, color=(0.8, 0.8, 0.8), rough=0.7, metal=0.0, alpha=1.0, emit=0.0):
    m = bpy.data.materials.new(name)
    nt, bsdf = principled(m)
    if png:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(png, check_existing=True)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Alpha"].default_value = alpha
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def add_object(coll, name, me, mat):
    if mat and not me.materials:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def mesh_from(name, verts, faces, uvs, flat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, p)) for p in verts], [], faces)
    layer = me.uv_layers.new(name="UVMap")
    for i, poly in enumerate(me.polygons):
        poly.use_smooth = not (flat and flat[i])
        for k, li in enumerate(poly.loop_indices):
            layer.data[li].uv = uvs[i][k]
    me.update()
    return me


def write_png(path, rgb):
    """8-bit RGB PNG from an (h, w, 3) array, stdlib only."""
    rgb = np.clip(np.asarray(rgb, np.float32) + 0.5, 0, 255).astype(np.uint8)
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- meshes and hulls

def corner_normal(me, li):
    try:
        return me.corner_normals[li].vector
    except AttributeError:  # pre-4.1 API
        return me.loops[li].normal


def write_smd(path, bones, skin_bone, parts):
    """bones: [(name, parent index or -1, parent-relative origin)] with identity rotations. parts: [(object, material)]
    weighted 100 % to skin_bone, or [(object, material, bone index)] for a rig whose parts move separately. Vertices
    stay in model space. Counter-clockwise triangles are front faces."""
    lines = ["version 1", "nodes"]
    lines += [f'{i} "{name}" {parent}' for i, (name, parent, _) in enumerate(bones)]
    lines += ["end", "skeleton", "time 0"]
    lines += [f"{i} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f} 0.000000 0.000000 0.000000" for i, (_, _, p) in enumerate(bones)]
    lines += ["end", "triangles"]
    tris = 0
    for ob, mat, *bone in parts:
        b = bone[0] if bone else skin_bone
        me = ob.data
        me.calc_loop_triangles()
        uv = me.uv_layers.active.data
        for tri in me.loop_triangles:
            lines.append(mat)
            for li in tri.loops:
                p = me.vertices[me.loops[li].vertex_index].co
                n = corner_normal(me, li)
                t = uv[li].uv
                lines.append(f"{b} {p.x:.6f} {p.y:.6f} {p.z:.6f} {n.x:.6f} {n.y:.6f} {n.z:.6f} "
                             f"{t.x:.6f} {t.y:.6f} 1 {b} 1.000000")
            tris += 1
    lines.append("end")
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return tris


def support_points(objects, count):
    """Extreme vertices along Fibonacci-sphere directions: few enough that ModelDoc keeps the hull as authored
    (re-fitting a dense hull to its vertex budget overshot a knife tip by 2.6")."""
    pts = np.array([tuple(v.co) for ob in objects for v in ob.data.vertices])
    golden = math.pi * (3.0 - math.sqrt(5.0))
    picked = set()
    for i in range(count):
        dz = 1.0 - 2.0 * (i + 0.5) / count
        rr = math.sqrt(1.0 - dz * dz)
        picked.add(int(np.argmax(pts @ np.array([rr * math.cos(golden * i), rr * math.sin(golden * i), dz]))))
    return [Vector(pts[i]) for i in sorted(picked)]


def convex_hull(points):
    """BMesh holding only the convex hull of `points`; the caller frees it."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=list(bm.verts))
    junk = list(dict.fromkeys(v for v in res["geom_interior"] + res["geom_unused"] if isinstance(v, bmesh.types.BMVert)))
    bmesh.ops.delete(bm, geom=junk, context="VERTS")
    bm.verts.index_update()
    return bm


def write_hull_dmx(path, model_name, points, mtl):
    """Unskinned model-space hull as KV2 DMX, bound with parent_bone in the VMDL. An SMD hull compiles rotated
    90 deg about Z (a render SMD does not), so hulls stay DMX."""
    bm = convex_hull(points)
    positions = [f'"{v.co.x:.6f} {v.co.y:.6f} {v.co.z:.6f}"' for v in bm.verts]
    faces = [str(i) for f in bm.faces for i in [v.index for v in f.verts] + [-1]]
    bm.free()

    ids = (str(uuid.uuid5(uuid.NAMESPACE_OID, f"{model_name}/{k}")) for k in itertools.count())  # stable reruns
    gid = lambda: next(ids)
    model, dag, vdata = gid(), gid(), gid()
    q = lambda items: ",\n".join(f"\t\t{i}" if i.startswith('"') else f'\t\t"{i}"' for i in items)
    xform = lambda: f'"DmeTransform"\n\t{{\n\t\t"id" "elementid" "{gid()}"\n\t\t"position" "vector3" "0 0 0"\n' \
                    f'\t\t"orientation" "quaternion" "0 0 0 1"\n\t}}'
    text = f'''<!-- dmx encoding keyvalues2 4 format model 22 -->
"DmElement"
{{
	"id" "elementid" "{gid()}"
	"name" "string" "root"
	"skeleton" "element" "{model}"
	"model" "element" "{model}"
}}

"DmeModel"
{{
	"id" "elementid" "{model}"
	"name" "string" "{model_name}"
	"transform" {xform()}
	"shape" "element" ""
	"visible" "bool" "1"
	"children" "element_array" [ "element" "{dag}" ]
	"jointList" "element_array" [ "element" "{dag}" ]
	"baseStates" "element_array"
	[
		"DmeTransformsList"
		{{
			"id" "elementid" "{gid()}"
			"transforms" "element_array" [ {xform()} ]
		}}
	]
	"axisSystem" "DmeAxisSystem"
	{{
		"id" "elementid" "{gid()}"
		"upAxis" "int" "3"
		"forwardParity" "int" "1"
		"coordSys" "int" "0"
	}}
}}

"DmeDag"
{{
	"id" "elementid" "{dag}"
	"name" "string" "hull"
	"transform" {xform()}
	"shape" "DmeMesh"
	{{
		"id" "elementid" "{gid()}"
		"name" "string" "hull"
		"bindState" "element" ""
		"currentState" "element" "{vdata}"
		"baseStates" "element_array" [ "element" "{vdata}" ]
		"deltaStates" "element_array" [ ]
		"faceSets" "element_array"
		[
			"DmeFaceSet"
			{{
				"id" "elementid" "{gid()}"
				"name" "string" "hull faces"
				"faces" "int_array"
				[
{q(faces)}
				]
				"material" "DmeMaterial"
				{{
					"id" "elementid" "{gid()}"
					"name" "string" "material"
					"mtlName" "string" "{mtl}"
				}}
			}}
		]
		"deltaStateWeights" "vector2_array" [ ]
		"deltaStateWeightsLagged" "vector2_array" [ ]
		"visible" "bool" "1"
	}}
	"visible" "bool" "1"
	"children" "element_array" [ ]
}}

"DmeVertexData"
{{
	"id" "elementid" "{vdata}"
	"name" "string" "bind"
	"vertexFormat" "string_array" [ "position$0" ]
	"jointCount" "int" "0"
	"flipVCoordinates" "bool" "0"
	"position$0" "vector3_array"
	[
{q(positions)}
	]
	"position$0Indices" "int_array"
	[
{q(str(i) for i in range(len(positions)))}
	]
}}
'''
    with open(path, "w", newline="\n") as fh:
        fh.write(text)
    return len(positions)


def bounds(objects):
    pts = np.array([tuple(v.co) for ob in objects for v in ob.data.vertices])
    return pts.min(0), pts.max(0)


def fmt(v):
    return "({:.3f},{:.3f},{:.3f})".format(*v)


# ---------------------------------------------------------------- ModelDoc and Material Editor files

class Raw(str):
    """A KV3 value written verbatim (resource references)."""


def kv3(value, ind=0):
    """KV3 text in ModelDoc's own layout: blocks for dicts and lists of dicts, inline numeric and empty lists."""
    t = "\t" * ind
    inline = lambda x: isinstance(x, list) and all(not isinstance(e, (dict, list)) for e in x)
    if isinstance(value, dict):
        lines = [t + "{"]
        for k, v in value.items():
            if isinstance(v, (dict, list)) and not inline(v):
                lines += [f"{t}\t{k} = ", kv3(v, ind + 1)]
            else:
                lines.append(f"{t}\t{k} = {kv3_scalar(v)}")
        return "\n".join(lines + [t + "}"])
    return "\n".join([t + "["] + [kv3(v, ind + 1) + "," for v in value] + [t + "]"])


def kv3_scalar(v):
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        return "[ " + ", ".join(kv3_scalar(e) for e in v) + " ]" if v else "[  ]"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    s = f"{float(v) + 0.0:.6f}".rstrip("0")  # fixed point like ModelDoc (never 1.9e-05); + 0.0 folds -0.0
    return s + "0" if s.endswith(".") else s


def write_vmdl(path, children):
    root = {"rootNode": {"_class": "RootNode", "children": children, "model_archetype": "",
                         "primary_associated_entity": "", "anim_graph_name": "",
                         "document_sub_type": "ModelDocSubType_None"}}
    head = ("<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
            "format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write(head + "\n" + kv3(root) + "\n")


def material_group(remaps):
    """remaps: [(material name in the mesh file, vmat path)]."""
    return {"_class": "MaterialGroupList", "children": [{
        "_class": "DefaultMaterialGroup", "remaps": [{"from": f"{a}.vmat", "to": b} for a, b in remaps],
        "use_global_default": False, "global_default_material": ""}]}


def render_mesh(filename, scale=1.0, name="body"):
    mesh = {"_class": "RenderMeshFile", "name": name, "filename": filename, "import_scale": scale,
            "import_filter": {"exclude_by_default": False, "exception_list": []}}
    if name is None:
        del mesh["name"]
    return {"_class": "RenderMeshList", "children": [mesh]}


def attachment(name, parent, origin, angles=(0.0, 0.0, 0.0)):
    return {"_class": "Attachment", "name": name, "ignore_rotation": False, "parent_bone": parent,
            "relative_origin": [float(c) for c in origin], "relative_angles": [float(c) for c in angles], "weight": 1.0}


def animations(*names):
    return {"_class": "AnimationList", "children": [{"_class": "AnimBindPose", "name": n} for n in names]}


def hulls(files, parent, scale=1.0, merge_angle=0.0):
    """files: [(name, mesh file, surface prop)]. maxHullVertices 0 keeps every authored hull vertex."""
    return {"_class": "PhysicsShapeList", "children": [{
        "_class": "PhysicsHullFile", "name": name, "parent_bone": parent, "surface_prop": surf,
        "collision_prop": "default", "tool_material": "", "recenter_on_parent_bone": False,
        "offset_origin": [0.0, 0.0, 0.0], "offset_angles": [0.0, 0.0, 0.0], "filename": mesh, "import_scale": scale,
        "faceMergeAngle": merge_angle, "maxHullVertices": 0, "import_mode": "SingleHull", "small_element_threshold": 0.0,
        "thin_element_threshold": 0.0, "optimization_algorithm": "QEM", "disable_region_svm": False,
        "import_filter": {"exclude_by_default": False, "exception_list": []}} for name, mesh, surf in files],
        "leave_body_collision_unmodified": False}


def bone(name, origin, children=None):
    b = {"_class": "Bone", "name": name, "origin": [float(c) for c in origin], "angles": [0.0, 0.0, 0.0],
         "do_not_discard": True}
    if children:
        b["children"] = children
    return b


def skeleton(bones):
    """Skeleton node from the flat write_smd bone list; the first bone is the root. Declare it even for a one-bone
    prop: without it an SMD root compiles rotated +90 deg about Z while a DMX hull keeps its frame."""
    nodes = {}
    for name, parent, pos in bones:
        nodes[name] = bone(name, pos)
        if parent >= 0:
            nodes[bones[parent][0]].setdefault("children", []).append(nodes[name])
    return {"_class": "Skeleton", "children": [nodes[bones[0][0]]]}


def write_weapon_vmdl(path, remaps, smd, hull, surface, attachment_list, sequences, nmskel, holster, hitbox, bones,
                      game_data=()):
    """Unified weapon model mirroring a stock one: its skeleton, attachments, bind-pose sequences, NmSkeleton
    reference and game data. hitbox: (mins, maxs) in weapon_offset space; game_data: extra [(game_class, keys)]."""
    r3 = lambda p: [round(float(c), 3) for c in p]
    data = [("prop_data", {"base": "Metal.Small", "allowstatic": False, "bakelighting": True, "damage_table": "",
                           "dmg.bullets": -1.0, "dmg.club": -1.0, "dmg.explosive": -1.0, "dmg.fire": -1.0,
                           "health": -1.0, "spawn_motion_disabled": False}),
            ("weapon_metadata", {"is_unified_model": True, "holster_attachment_preferred": holster[0],
                                 "holster_attachment_fallback": holster[1], "reloads_with_clips": True,
                                 "magazine_model": Raw('resource:""'), "fire_sequence_name": "", "fire_sequence_name_2": ""}),
            ("CPhysicsBodyGameMarkupData", {"m_PhysicsBodyMarkupByBoneName": {
                "weapon_offset": {"m_TargetBody": "weapon_offset", "m_Tag": ""}}})] + list(game_data)
    write_vmdl(path, [
        material_group(remaps),
        {"_class": "BoneMarkupList", "children": [], "bone_cull_type": "None"},
        render_mesh(smd),
        {"_class": "AttachmentList", "children": attachment_list},
        animations(*sequences),
        hulls([("body", hull, surface)], "weapon_offset"),
        {"_class": "NmSkeletonList", "children": [{"_class": "NmSkeletonReference", "filename": nmskel}]},
        {"_class": "GameDataList", "children": [{"_class": "GenericGameData", "name": "", "game_class": c, "game_keys": k}
                                                for c, k in data]},
        {"_class": "HitboxSetList", "children": [{"_class": "HitboxSet", "name": "default", "children": [{
            "_class": "Hitbox", "hitbox_mins": r3(hitbox[0]), "hitbox_maxs": r3(hitbox[1]), "name": "weapon_offset",
            "parent_bone": "weapon_offset", "surface_property": "weapon", "translation_only": False, "group_id": 0}]}]},
        skeleton(bones),
    ])


VMAT = '''{head}Layer0
{{
	shader "csgo_complex.vfx"

{translucent}	//---- Color ----
	g_flModelTintAmount "1.000"
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "{color}"

	//---- Fog ----
	g_bFogEnabled "1"

	//---- Lighting ----
	g_flMetalness "{metal:.3f}"
	TextureRoughness "[{rough:.6f} {rough:.6f} {rough:.6f} 0.000000]"

	//---- Normal Map ----
	TextureNormal "{normal}"
{self_illum}}}
'''


def write_vmat(path, color, rough, metal=0.0, comment="", normal="materials/default/default_normal.tga",
               alpha_test=None, self_illum=None):
    """csgo_complex material in Material Editor's layout. alpha_test: (reference, translucency texture), the alpha
    is packed into the colour texture; self_illum: (brightness, tint rgb), unmasked."""
    translucent = self_lit = ""
    if alpha_test:
        translucent = (f'\t//---- Translucent ----\n\tF_ALPHA_TEST 1\n\tg_flAlphaTestReference "{alpha_test[0]:.3f}"\n'
                       f'\tTextureTranslucency "{alpha_test[1]}"\n\n')
    if self_illum:
        r, g, b = self_illum[1]
        self_lit = (f'\n\t//---- Self Illum ----\n\tF_SELF_ILLUM 1\n\tg_flSelfIllumAlbedoFactor "0.000"\n'
                    f'\tg_flSelfIllumBrightness "{self_illum[0]:.3f}"\n\tg_flSelfIllumScale "1.000"\n'
                    f'\tg_vSelfIllumTint "[{r:.6f} {g:.6f} {b:.6f} 0.000000]"\n'
                    f'\tTextureSelfIllumMask "[1.000000 1.000000 1.000000 0.000000]"\n')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write(VMAT.format(head=f"// {comment}\n\n" if comment else "", translucent=translucent, color=color,
                            metal=metal, rough=rough, normal=normal, self_illum=self_lit))


if __name__ == "__main__":
    import tempfile
    assert [kv3_scalar(v) for v in (1.0, -0.0, 0.393701, 1.9e-05, 10.0, 3, True, "a", [], [0.0, -1.5])] == \
        ["1.0", "0.0", "0.393701", "0.000019", "10.0", "3", "true", '"a"', "[  ]", "[ 0.0, -1.5 ]"]
    assert kv3({"a": {"b": 1}, "c": [{"d": Raw('resource:""')}], "e": [1, 2]}) == \
        '{\n\ta = \n\t{\n\t\tb = 1\n\t}\n\tc = \n\t[\n\t\t{\n\t\t\td = resource:""\n\t\t},\n\t]\n\te = [ 1, 2 ]\n}'
    tet = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    ob = bpy.data.objects.new("tet", mesh_from("tet", tet, [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)], [[(0, 0)] * 3] * 4))
    with tempfile.TemporaryDirectory() as tmp:
        smd = os.path.join(tmp, "tet.smd")
        assert write_smd(smd, [("root", -1, (0.0, 0.0, 0.0))], 0, [(ob, "m")]) == 4
        lines = open(smd).read().split("\n")
        assert lines.count("m") == 4 and sum(len(s.split()) == 12 for s in lines) == 12
        write_smd(smd, [("root", -1, (0.0, 0.0, 0.0)), ("part", 0, (0.0, 0.0, 1.0))], 0, [(ob, "m", 1)])
        assert sum(s.startswith("1 ") and s.endswith(" 1 1 1.000000") for s in open(smd).read().split("\n")) == 12
        dmx = [os.path.join(tmp, f"tet{k}.dmx") for k in (0, 1)]
        assert [write_hull_dmx(p, "tet_hull", support_points([ob], 24), "$default") for p in dmx] == [4, 4]
        assert open(dmx[0]).read() == open(dmx[1]).read(), "hull DMX must be byte-identical across runs"
    print("source2_kit self-check ok")
