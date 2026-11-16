"""Builds an example butterfly knife (balisong) on the stock butterfly frame (weapon_knife_butterfly, defindex 515): a
hand-written SMD whose parts ride the stock moving bones, a KV2 DMX hull, the VMDL, its VMATs and colour swatches.
Style inspired by "Butterfly Knife | Dragonian" by clegfx; no geometry used.

Run:  blender -b --factory-startup --python build_example_butterfly.py -- --addon-root <content/csgo_addons/<addon>>
          --out <addon>/rawmodels/example_butterfly [--render <dir>]
Geometry is Source model space in inches, built open (the bind pose). Measured off the stock model: the blade turns
about a pin in the front handle, the rear handle about a pin in the blade, the latch about a pin in the rear butt, all
about +Y; the blade lies flat in XZ. The front handle is skinned to weapon_offset, like the stock mesh. Stock clips
close the knife by turning the blade ~180 deg and the rear ~-180 deg, which moves the rear handle to the other side of
the front one; so each handle is a pair of side plates the blade passes between, and the blade outline is sized to
where the closed handles lie. POSES holds stock clip frames; --render previews them and every build prints part
overlaps for them. The SMD is written by hand so the stock bones keep their exact identity rest transforms. All
surface detail is geometry: CS2's normal-map green convention is unverified.
"""
import math
import os
import sys

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import tessellate_polygon

import source2_kit as kit

NAME = "example_butterfly"
MAT_REL = "weapons/custom/knife/example_butterfly/materials"
VMDL = "weapons/custom/knife/example_butterfly/example_butterfly.vmdl"
MATERIALS = {  # swatch rgb, roughness, metalness
    "blade": ((182, 186, 192), 0.28, 1.0),
    "handle": ((58, 54, 50), 0.40, 0.8),
    "scale": ((30, 104, 74), 0.34, 0.6),
}
# weapons/models/knife/knife_butterfly/weapon_knife_butterfly.vmdl_c bones in -b DATA order (m_modelSkeleton); rotations identity.
BONES = [("weapon", -1, (0.000004, 0.0, 0.5)), ("weapon_offset", 0, (0.0, 0.0, 0.0)),
         ("front", 1, (-0.173383, 0.0, 1.519639)), ("blade", 2, (0.036114, -0.021928, 0.009469)),
         ("rear", 3, (0.669104, 0.021931, 0.409437)), ("lock", 4, (0.929171, -0.02193, -6.213495)),
         ("ag1_hand_r", 1, (-0.000006, 0.000002, 0.499998))]
OFFSET, BLADE, REAR, LOCK = 1, 3, 4, 5   # the stock mesh is skinned to these four; front carries nothing
BONE_Z = 0.5         # weapon_offset's model-space height; the hitbox is bone-relative
# Attachments as -d decompiles them (-b MDAT has quaternions), NmSkeleton and holsters (-b DATA), hull surface (-b RED2).
ATTACHMENTS = [kit.attachment("weapon_holster_center", "weapon_offset", (0.0, 0.0, 1.517824)),
               kit.attachment("camera_inventory", "weapon_offset", (2.530238, 14.195025, 0.400994),
                              (-1.911568, -98.573792, 68.284584)),
               kit.attachment("stattrak", "blade", (0.532586, 0.057988, 3.655856),
                              (88.468796, -174.456543, -165.276718)),
               kit.attachment("nametag", "rear", (0.015184, 0.365096, -3.632685),
                              (82.620995, 6.710943, 6.766439))]
NMSKEL = "animation/skeletons/weapons/knife_butterfly.vnmskel"
HOLSTER = ("knife", "knife")
SURFACE = "weaponknife"
# Blade, rear and lock angles (deg about +Y) at stock clip frames, decoded from the clips' compressed pose data.
POSES = {"idle": (0.0, 0.0, 43.3),            # idle1: open, latch over the front butt
         "closed": (169.8, -171.4, 39.0),     # draw frame 0
         "flip": (-155.0, -88.3, 39.0),       # draw frame 12
         "fan": (-73.7, -70.5, -104.7)}       # lookat01 frame 6
FIT_ONLY = {"shut": (180.0, -180.0, 39.0)}    # fully closed: the blade must sit between the plates

Y_IN, Y_OUT = 0.16, 0.38    # side plates; blade (|y| <= 0.065) and latch (0.07) pass between them
HALF_W = 0.30               # handle half-width; the pins sit 0.67 apart across, so only the curved butts graze when shut
HANDLE_LEN = 6.75           # pin to butt; the latch then reaches between the front plates at the idle angle
BEND_K, BEND_D = 0.047, 2.5  # handles curve toward +X below BEND_D, like the stock grip the hand closes on
H_TIP = 5.8                 # blade tip above the front pin; closed, it stops short of the front spacer
SPINE = [(0.0, -0.30), (1.0, -0.30), (2.5, -0.31), (3.8, -0.33), (4.4, -0.30), (5.0, -0.22), (5.4, -0.19),
         (5.65, -0.22), (H_TIP, -0.26)]       # (height above the front pin, x)
EDGE = [(0.62, 0.60), (1.0, 0.60), (1.5, 0.575), (2.3, 0.62), (3.2, 0.68), (4.0, 0.64), (4.7, 0.47),
        (5.25, 0.22), (5.6, -0.03), (H_TIP, -0.26)]
SPIKES = (0.85, 0.275, [0.07, 0.09, 0.09, 0.07])   # dragon-back teeth on the spine: start, pitch, heights


def bone_origin(i):
    p = Vector()
    while i >= 0:
        p += Vector(BONES[i][2])
        i = BONES[i][1]
    return p


PB, PR, PL = bone_origin(BLADE), bone_origin(REAR), bone_origin(LOCK)


def smooth(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def catmull(points, step):
    """Catmull-Rom resample of (s, value) control points every `step` along s."""
    out = []
    pts = [points[0]] + points + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        n = max(1, int(math.ceil((p2[0] - p1[0]) / step)))
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (p2[j] - p0[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (3 * p1[j] - p0[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(2)))
    out.append(points[-1])
    return np.array(out)


def curve(points):
    c = catmull(points, 0.01)
    return lambda s: np.interp(s, np.maximum.accumulate(c[:, 0]), c[:, 1])


def pose_matrices(blade, rear, lock):
    turn = lambda p, a: Matrix.Translation(p) @ Matrix.Rotation(math.radians(a), 4, "Y") @ Matrix.Translation(-p)
    mb = turn(PB, blade)
    mr = mb @ turn(PR, rear)
    return {OFFSET: Matrix(), BLADE: mb, REAR: mr, LOCK: mr @ turn(PL, lock)}


# ---------------------------------------------------------------- mesh helpers

def finish(name, bm, angle=35.0, closed=True):
    """BMesh to mesh: outward normals, smooth shading split at creases sharper than `angle`, box-projected UVs (the
    swatch ignores UVs, but zero-area UV triangles break the tangent pass)."""
    if closed:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bad = sum(1 for e in bm.edges if not e.is_manifold)
        if bad:
            print(f"WARNING {name} non_manifold_edges={bad}")
    bm.normal_update()
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = e.is_manifold and e.calc_face_angle() < math.radians(angle)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        ax = max(range(3), key=lambda k: abs(f.normal[k]))
        a, b = [k for k in range(3) if k != ax]
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co[a] * 0.5, loop.vert.co[b] * 0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def oriented(loop, ccw):
    """(x, z) loop wound counter-clockwise (outline) or clockwise (hole), so the material is always on its left."""
    a = np.asarray(loop, float)
    area = 0.5 * float(np.sum(a[:, 0] * np.roll(a[:, 1], -1) - np.roll(a[:, 0], -1) * a[:, 1]))
    return a if (area > 0) == ccw else a[::-1]


def inset(loop, c):
    t = np.roll(loop, -1, axis=0) - np.roll(loop, 1, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    return loop + c * np.stack([-t[:, 1], t[:, 0]], axis=1)


def prism(name, loops, y0, y1, bevel):
    """Solid between y0 and y1 from (x, z) loops, the first the outline and the rest holes, edges chamfered."""
    loops = [oriented(lp, i == 0) for i, lp in enumerate(loops)]
    bm = bmesh.new()
    caps = {y0: [], y1: []}
    for lp in loops:
        rings = [(inset(lp, bevel), y1), (lp, y1 - bevel), (lp, y0 + bevel), (inset(lp, bevel), y0)]
        vs = [[bm.verts.new((x, y, z)) for x, z in pts] for pts, y in rings]
        n = len(lp)
        for r in range(3):
            for i in range(n):
                k = (i + 1) % n
                bm.faces.new((vs[r][i], vs[r][k], vs[r + 1][k], vs[r + 1][i]))
        caps[y1].append(vs[0])
        caps[y0].append(vs[3])
    for ring_list in caps.values():
        flat = [v for ring in ring_list for v in ring]
        for tri in tessellate_polygon([[Vector((v.co.x, v.co.z, 0.0)) for v in ring] for ring in ring_list]):
            bm.faces.new([flat[i] for i in tri])
    return finish(name, bm)


def lathe_y(name, centre, profile, segs=28):
    """Surface of revolution about a Y-parallel axis through centre (x, z); profile (radius, y), poles at radius 0."""
    bm = bmesh.new()
    rings = []
    for r, y in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((centre[0], y, centre[1]))])
        else:
            rings.append([bm.verts.new((centre[0] + r * math.cos(math.tau * j / segs), y,
                                        centre[1] + r * math.sin(math.tau * j / segs))) for j in range(segs)])
    for a, b in zip(rings, rings[1:]):
        for j in range(segs):
            k = (j + 1) % segs
            if len(a) == 1:
                bm.faces.new((a[0], b[k], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[j], a[k], b[0]))
            else:
                bm.faces.new((a[j], a[k], b[k], b[j]))
    return finish(name, bm)


# ---------------------------------------------------------------- handles

def bend(d):
    return BEND_K * max(0.0, d - BEND_D) ** 2


def handle_xz(pin, d, l):
    """Handle plate coordinates (d down the handle from its pin, l across toward +X) to model (x, z)."""
    s = 2.0 * BEND_K * max(0.0, d - BEND_D)
    n = 1.0 / math.sqrt(1.0 + s * s)
    return pin.x + bend(d) + l * n, pin.z - d + l * s * n


def handle_loop(pin, w_plus, w_minus):
    """Outline: round cap on the pin, sides at the given half-widths, an elliptic cap at the butt."""
    cap_r = HALF_W
    d_end = HANDLE_LEN - cap_r
    pts = [(-cap_r * math.sin(f), cap_r * math.cos(f)) for f in np.linspace(0.0, math.pi, 25)[:-1]]
    ds = np.arange(0.0, d_end, 0.05)
    pts += [(d, -w_minus(d)) for d in ds]
    mid, rl = 0.5 * (w_plus(d_end) - w_minus(d_end)), 0.5 * (w_plus(d_end) + w_minus(d_end))
    pts += [(d_end + cap_r * math.sin(f), mid - rl * math.cos(f)) for f in np.linspace(0.0, math.pi, 25)[:-1]]
    pts += [(d, w_plus(d)) for d in ds[::-1][:-1]]
    return [handle_xz(pin, d, l) for d, l in pts]


def capsule(pin, a, b, r, n=10):
    """Slot between plate points a and b, (d, l) each."""
    a, b = np.array(a), np.array(b)
    t = (b - a) / np.linalg.norm(b - a)
    side = np.array([-t[1], t[0]])
    f = np.linspace(0.0, math.pi, n)
    pts = [b + r * (math.cos(x) * side + math.sin(x) * t) for x in f]
    pts += [a - r * (math.cos(x) * side + math.sin(x) * t) for x in f]
    return [handle_xz(pin, d, l) for d, l in pts]


def claw_slots(pin):
    """Three slanted slots through each plate below the grip, like claw marks."""
    half = 0.2 * np.array([math.cos(math.radians(55)), math.sin(math.radians(55))])
    return [capsule(pin, (dc, 0.0) - half, (dc, 0.0) + half, 0.055) for dc in (4.15, 4.57, 4.99)]


def plates(name, pin, w_plus):
    outline = handle_loop(pin, w_plus, lambda d: HALF_W)
    holes = claw_slots(pin)
    meshes = [prism(f"{name}_{s}", [outline] + holes, *ys, 0.02) for s, ys in
              (("pos", (Y_IN, Y_OUT)), ("neg", (-Y_OUT, -Y_IN)))]
    return join(name, meshes)


def join(name, meshes):
    bm = bmesh.new()
    for me in meshes:
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def scales(name, pin):
    """Overlapping scales on both outer plate faces, free edge toward the butt; their top and sides sink 0.01 into
    the plate."""
    nu, nv, depth, keel = 4, 2, 0.035, 0.006
    bm = bmesh.new()
    for sign in (1.0, -1.0):
        base = sign * (Y_OUT - 0.010)
        for row, d0 in enumerate(np.arange(0.62, 3.56, 0.125)):
            offsets = (-0.14, 0.0, 0.14) if row % 2 == 0 else (-0.21, -0.07, 0.07, 0.21)
            for c in offsets:
                hw = min(0.08, HALF_W - 0.03 - abs(c))
                grid = []
                for v in np.linspace(0.0, 1.0, nv + 1):
                    row_vs = []
                    for u in np.linspace(-1.0, 1.0, nu + 1):
                        rim = math.sqrt(max(0.0, 1.0 - u * u))
                        d = d0 + v * 0.2 * (0.55 + 0.45 * rim)
                        h = depth * v ** 0.7 * rim ** 0.4 + keel * math.exp(-(u / 0.25) ** 2) * v
                        x, z = handle_xz(pin, d, c + u * hw)
                        row_vs.append(bm.verts.new((x, base + sign * h, z)))
                    grid.append(row_vs)
                grid.append([bm.verts.new((v.co.x, base - sign * 0.004, v.co.z)) for v in grid[-1]])  # lip
                for i in range(len(grid) - 1):
                    for j in range(nu):
                        quad = (grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j])  # faces +Y
                        bm.faces.new(quad if sign > 0 else quad[::-1])
    return finish(name, bm, angle=50.0, closed=False)


def spacer(name, pin, d0, d1):
    w = HALF_W - 0.03
    loop = [handle_xz(pin, d, w) for d in np.linspace(d0, d1, 5)]
    loop += [handle_xz(pin, d, -w) for d in np.linspace(d1, d0, 5)]
    return prism(name, [loop], -Y_IN - 0.01, Y_IN + 0.01, 0.01)


def pin(name, centre, r, head):
    """Pin with a domed head proud of each plate face; its shaft runs through the blade or latch it carries."""
    top = Y_OUT + 0.035
    prof = [(0.0, -top), (head * 0.6, -top + 0.004), (head * 0.92, -top + 0.017), (head, -Y_OUT + 0.003),
            (head, -Y_OUT + 0.01), (r, -Y_OUT + 0.01), (r, Y_OUT - 0.01), (head, Y_OUT - 0.01), (head, Y_OUT - 0.003),
            (head * 0.92, top - 0.017), (head * 0.6, top - 0.004), (0.0, top)]
    return lathe_y(name, (centre.x, centre.z), prof)


# ---------------------------------------------------------------- blade and latch

def tang_interval(h_values, r=0.25):
    """x-extent of the convex hull of the two pin bosses, (x, height above the front pin)."""
    ang = np.linspace(0.0, math.tau, 96, endpoint=False)
    pts = np.concatenate([np.stack([cx + r * np.cos(ang), cz + r * np.sin(ang)], 1)
                          for cx, cz in ((PB.x, 0.0), (PR.x, PR.z - PB.z))])
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    hull = []
    for seq in (pts, pts[::-1]):
        part = []
        for p in seq:
            while len(part) >= 2 and cross(part[-2], part[-1], p) <= 0:
                part.pop()
            part.append(p)
        hull += part[:-1]
    out = []
    for h in h_values:
        xs = [a[0] + (h - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) for a, b in zip(hull, hull[1:] + hull[:1])
              if min(a[1], b[1]) <= h <= max(a[1], b[1]) and a[1] != b[1]]
        out.append((min(xs), max(xs)) if xs else (np.nan, np.nan))
    return np.array(out)


def spikes(h):
    start, pitch, heights = SPIKES
    k = np.floor((h - start) / pitch).astype(int)
    frac = (h - start) / pitch - k
    ok = (k >= 0) & (k < len(heights))
    return np.where(ok, np.take(heights, np.clip(k, 0, len(heights) - 1)) * frac ** 1.6, 0.0)


def build_blade():
    hs = np.concatenate([np.arange(-0.246, 0.80, 0.02), np.arange(0.80, 2.0, 0.011), np.arange(2.0, H_TIP - 0.02, 0.035),
                         [H_TIP - 0.012]])
    tang = tang_interval(hs)
    spine, edge = curve(SPINE), curve(EDGE)
    lo = np.fmin(tang[:, 0], np.where(hs >= 0.0, spine(hs) - spikes(hs), np.nan))
    hi = np.fmax(tang[:, 1], np.where(hs >= EDGE[0][0], edge(hs), np.nan))
    us = np.array([0, .03, .08, .14, .2, .24, .27, .3, .34, .42, .5, .6, .7, .8, .9, .96, 1.0])
    H, U = np.meshgrid(hs, us, indexing="ij")
    width = (hi - lo)[:, None]
    X = lo[:, None] + U * width
    spine_t = 0.065 * (1.0 - 0.55 * smooth(3.4, H_TIP, H))
    grind = smooth(0.62, 0.8, H) * np.clip((U - 0.42) / 0.58, 0.0, 1.0)
    fuller = 0.022 * np.exp(-((U - 0.27) * width / 0.045) ** 2) * smooth(0.95, 1.3, H) * (1.0 - smooth(3.4, 3.9, H))
    T = np.maximum(spine_t * (1.0 - grind) - fuller, 0.004)

    bm = bmesh.new()
    nh, nu = H.shape
    top = [[bm.verts.new((X[i, j], T[i, j], PB.z + H[i, j])) for j in range(nu)] for i in range(nh)]
    bot = [[bm.verts.new((X[i, j], -T[i, j], PB.z + H[i, j])) for j in range(nu)] for i in range(nh)]
    tip = bm.verts.new((SPINE[-1][1], 0.0, PB.z + H_TIP))
    for i in range(nh - 1):
        for j in range(nu - 1):
            bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]))
            bm.faces.new((bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]))
        for j in (0, nu - 1):
            bm.faces.new((top[i][j], top[i + 1][j], bot[i + 1][j], bot[i][j]))
    for j in range(nu - 1):
        bm.faces.new((top[0][j], bot[0][j], bot[0][j + 1], top[0][j + 1]))
        bm.faces.new((top[-1][j], top[-1][j + 1], tip))
        bm.faces.new((bot[-1][j + 1], bot[-1][j], tip))
    for j in (0, nu - 1):
        bm.faces.new((top[-1][j], bot[-1][j], tip))
    return finish("blade", bm)


LATCH = [(0.0, 0.0, 0.11), (0.0, -0.35, 0.085), (0.02, -0.70, 0.075), (-0.04, -0.98, 0.062), (-0.20, -1.12, 0.042),
         (-0.33, -1.09, 0.022)]   # (x, z) from the lock pin, half-width; the hook curls toward the front handle


def build_latch():
    """Talon latch, hanging from its pin in the bind pose; the idle angle swings the hook between the front plates."""
    x, z, w = (catmull([(i, p[k]) for i, p in enumerate(LATCH)], 0.05)[:, 1] for k in range(3))
    cl = np.stack([x, z], axis=1)
    t = np.gradient(cl, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    side = np.stack([-t[:, 1], t[:, 0]], axis=1)
    rounded = lambda i, sign: [cl[i] + w[i] * (-math.cos(a) * side[i] + sign * math.sin(a) * t[i])
                               for a in np.linspace(0.0, math.pi, 11)[1:-1]]
    loop = list(cl + side * w[:, None]) + rounded(-1, 1.0)[::-1] + list((cl - side * w[:, None])[::-1]) + rounded(0, -1.0)
    return prism("latch", [np.array(loop) + (PL.x, PL.z)], -0.07, 0.07, 0.01)


def build_parts():
    """{name: (mesh, material, bone)}"""
    rear_fin = lambda d: HALF_W + 0.17 * math.exp(-((d - 6.2) / 0.28) ** 2)  # houses the latch pin
    return {
        "blade": (build_blade(), "blade", BLADE),
        "front_plates": (plates("front_plates", PB, lambda d: HALF_W), "handle", OFFSET),
        "front_scales": (scales("front_scales", PB), "scale", OFFSET),
        "front_pin": (pin("front_pin", PB, 0.08, 0.13), "handle", OFFSET),
        "front_spacer": (spacer("front_spacer", PB, 5.95, 6.25), "handle", OFFSET),
        "rear_plates": (plates("rear_plates", PR, rear_fin), "handle", REAR),
        "rear_scales": (scales("rear_scales", PR), "scale", REAR),
        "rear_pin": (pin("rear_pin", PR, 0.08, 0.13), "handle", REAR),
        "lock_pin": (pin("lock_pin", PL, 0.06, 0.10), "handle", REAR),
        "latch": (build_latch(), "scale", LOCK),
    }


# ---------------------------------------------------------------- checks and previews

BODY = {OFFSET: "front", BLADE: "blade", REAR: "rear", LOCK: "latch"}
PIN_THROUGH = {("front_pin", "blade"), ("rear_pin", "blade"), ("lock_pin", "latch")}


def overlaps(objects, bones, pose):
    """Intersecting triangle pairs between parts on different bones, minus the pins through what they carry."""
    mats = pose_matrices(*pose)
    trees = {}
    for ob in objects:
        m = mats[bones[ob.name]]
        trees[ob.name] = BVHTree.FromPolygons([m @ v.co for v in ob.data.vertices],
                                              [tuple(p.vertices) for p in ob.data.polygons])
    out = {}
    for i, a in enumerate(objects):
        for b in objects[i + 1:]:
            if bones[a.name] == bones[b.name] or (a.name, b.name) in PIN_THROUGH or (b.name, a.name) in PIN_THROUGH:
                continue
            n = len(trees[a.name].overlap(trees[b.name]))
            if n:
                out[f"{a.name}/{b.name}"] = n
    return out


def apply_pose(objects, bones, pose):
    mats = pose_matrices(*pose)
    for ob in objects:
        ob.matrix_world = mats[bones[ob.name]]


def posed_bounds(objects):
    pts = np.array([tuple(ob.matrix_world @ v.co) for ob in objects for v in ob.data.vertices])
    return Vector(pts.min(0)), Vector(pts.max(0))


def add_camera(coll, name, target, direction, distance, lens=50):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    ob = bpy.data.objects.new(name, cd)
    ob.location = Vector(target) + Vector(direction).normalized() * distance
    kit.look_at(ob, target)
    coll.objects.link(ob)
    return ob


def setup_lights(coll, centre):
    for name, energy, loc in (("key", 9000.0, (14, 22, 18)), ("fill", 3500.0, (-16, 20, 2)), ("rim", 5000.0, (4, -22, 14)),
                              ("back", 3000.0, (-10, -20, -6))):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = energy, 10.0
        lo = bpy.data.objects.new(name, ld)
        lo.location = centre + Vector(loc)
        lo.rotation_euler = (centre - lo.location).to_track_quat("-Z", "Y").to_euler()
        coll.objects.link(lo)


# (pose, camera direction, framing: None = whole posed knife, else (target, distance), resolution)
SHOTS = {
    "idle": ("idle", (0.3, 1.0, 0.1), None, (640, 960)),
    "idle_back": ("idle", (-0.3, -1.0, 0.1), None, (640, 960)),
    "closed": ("closed", (0.3, 1.0, 0.1), None, (640, 960)),
    "shut": ("shut", (0.3, 1.0, 0.1), None, (640, 960)),
    "flip": ("flip", (0.2, 1.0, 0.15), None, (960, 720)),
    "fan": ("fan", (0.2, 1.0, 0.15), None, (960, 720)),
    "scales": ("idle", (0.35, 1.0, 0.25), ((0.25, 0.4, 0.6), 4.2), (960, 640)),
    "latch": ("idle", (0.5, 1.0, -0.35), ((0.95, 0.2, -4.2), 3.4), (960, 640)),
    "spine": ("idle", (-0.5, 1.0, 0.1), ((0.05, 0.0, 3.6), 3.8), (960, 640)),
}


def main():
    A = kit.cli(__doc__)
    addon = lambda rel: os.path.join(A.addon_root, *rel.split("/"))
    sc = kit.clear_scene(0.0254)

    os.makedirs(addon(MAT_REL), exist_ok=True)
    mats, remaps = {}, []
    for key, (rgb, rough, metal) in MATERIALS.items():
        name = f"{NAME}_{key}"
        swatch = addon(f"{MAT_REL}/{name}_color.png")
        kit.write_png(swatch, np.full((16, 16, 3), rgb))
        kit.write_vmat(addon(f"{MAT_REL}/{name}.vmat"), f"{MAT_REL}/{name}_color.png", rough, metal,
                       comment=f"Example butterfly knife: {key}, plain csgo_complex.")
        mats[key] = (name, kit.blender_material(name, swatch, rough=rough, metal=metal))
        remaps.append((name, f"{MAT_REL}/{name}.vmat"))

    coll = bpy.data.collections.new(NAME)
    sc.collection.children.link(coll)
    objects, bones, parts = [], {}, []
    for name, (me, mat, bone) in build_parts().items():
        ob = kit.add_object(coll, name, me, mats[mat][1])
        objects.append(ob)
        bones[name] = bone
        parts.append((ob, mats[mat][0], bone))

    tris = kit.write_smd(os.path.join(A.out, f"{NAME}.smd"), BONES, OFFSET, parts)
    hull_verts = kit.write_hull_dmx(os.path.join(A.out, f"{NAME}_hull.dmx"), f"{NAME}_hull",
                                    kit.support_points(objects, 40), "$" + SURFACE)
    lo, hi = kit.bounds(objects)
    per_part = ", ".join(f"{ob.name}={sum(len(p.vertices) - 2 for p in ob.data.polygons)}" for ob in objects)
    print(f"STATS tris={tris} ({per_part}) hull_verts={hull_verts}")
    print("PIVOTS blade={} rear={} lock={}".format(kit.fmt(PB), kit.fmt(PR), kit.fmt(PL)))
    print(f"BOUNDS model min={kit.fmt(lo)} max={kit.fmt(hi)}")
    hitbox = (lo - (0.0, 0.0, BONE_Z), hi - (0.0, 0.0, BONE_Z))
    print("HITBOX weapon_offset-space mins=[{:.3f}, {:.3f}, {:.3f}] maxs=[{:.3f}, {:.3f}, {:.3f}]".format(*hitbox[0], *hitbox[1]))
    for name, pose in {**POSES, **FIT_ONLY}.items():
        print(f"FIT {name} {overlaps(objects, bones, pose) or 'clear'}")
    kit.write_weapon_vmdl(addon(VMDL), remaps, A.out_rel + f"{NAME}.smd", A.out_rel + f"{NAME}_hull.dmx", SURFACE,
                          ATTACHMENTS, ("refPose",), NMSKEL, HOLSTER, hitbox, BONES)

    kit.setup_render((0.05, 0.05, 0.055), 64, (640, 960))
    preview = bpy.data.collections.new("preview")
    sc.collection.children.link(preview)
    setup_lights(preview, Vector((0.3, 0.0, 1.5)))
    kit.save_blend(os.path.join(A.out, f"{NAME}.blend"))
    if A.render:
        poses = {**POSES, **FIT_ONLY}
        for shot, (pose, direction, framing, res) in SHOTS.items():
            apply_pose(objects, bones, poses[pose])
            if framing is None:
                p_lo, p_hi = posed_bounds(objects)
                target, distance = (p_lo + p_hi) / 2, 1.25 * max(p_hi - p_lo) / (2 * math.tan(math.radians(19.8)))
            else:
                target, distance = framing
            sc.camera = add_camera(preview, f"cam_{shot}", target, direction, distance)
            sc.render.resolution_x, sc.render.resolution_y = res
            sc.render.filepath = os.path.join(A.render, f"{NAME}_{shot}.png")
            bpy.ops.render.render(write_still=True)
            print("RENDERED", sc.render.filepath)


main()
