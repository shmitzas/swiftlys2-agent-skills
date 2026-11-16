"""Builds a Christmas tree map decoration through the FBX route: fir tree, baubles, fairy lights, star and presents,
a convex physics hull, the VMDL and its VMATs.

Run make_textures.py with the same --addon-root first (the .blend previews its PNGs), then
    blender -b --factory-startup --python build_christmas_tree.py -- --addon-root <content/csgo_addons/<addon>>
        --out <addon>/rawmodels/christmas_tree [--render <dir>]
Writes christmas_tree.blend, christmas_tree.fbx (render) and christmas_tree_phys.fbx (hull) into --out.
Built in metres; the VMDL's import_scale converts to inches.
"""
import bisect
import math
import os
import random
import sys

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import source2_kit as kit

MAT_REL = "materials/christmas_tree"
VMDL = "models/props/xmas/christmas_tree.vmdl"
FBX_SCALE = 0.393701  # this export writes centimetres and ModelDoc reads one as a unit: this makes them inches

rng = random.Random(20261225)
TAU = math.tau
Z = Vector((0.0, 0.0, 1.0))
# Geometry is designed facing +X and baked facing Blender's front (-Y): ModelDoc maps
# Blender -Y to Source +X, so the star faces the model's forward axis in game.
FRONT = Matrix.Rotation(-math.pi / 2, 3, "Z")

H_TIP = 2.45   # top of the needles; the star sits above
H0 = 0.30      # lowest whorl
R_MAX = 0.70   # crown radius at the lowest whorl


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def crown_radius(h):
    t = max(0.0, min(1.0, (h - H0) / (H_TIP - H0)))
    return R_MAX * (1.0 - t) ** 0.92 * (0.86 + 0.14 * smoothstep(0.0, 0.1, t))


def trunk_radius(h):
    return lerp(0.05, 0.012, max(0.0, min(1.0, h / (H_TIP - 0.2))))


# ---------------------------------------------------------------- mesh building

class MB:
    """Polygons with per-corner UVs and optional per-corner normals, one material."""

    def __init__(self):
        self.verts, self.faces, self.uvs, self.normals, self.smooth = [], [], [], [], []

    def vert(self, co):
        self.verts.append(tuple(co))
        return len(self.verts) - 1

    def face(self, idx, uv, normals=None, smooth=True):
        self.faces.append(tuple(idx))
        self.uvs.append(uv)
        self.normals.append(normals)
        self.smooth.append(smooth)

    def build(self, name, mat, coll):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(FRONT @ Vector(v)) for v in self.verts], [], self.faces)
        uvl = me.uv_layers.new(name="UVMap")
        for poly, uv, sm in zip(me.polygons, self.uvs, self.smooth):
            poly.use_smooth = sm
            for k, li in enumerate(poly.loop_indices):
                uvl.data[li].uv = uv[k]
        if any(n is not None for n in self.normals):
            loop_n = [(0.0, 0.0, 1.0)] * len(me.loops)
            for poly, ns in zip(me.polygons, self.normals):
                for k, li in enumerate(poly.loop_indices):
                    loop_n[li] = tuple(FRONT @ ns[k]) if ns else tuple(poly.normal)
            me.normals_split_custom_set(loop_n)
        me.update()
        return kit.add_object(coll, name, me, mat)


def sphere(mb, c, r, segs=12, rings=8, sz=1.0):
    top, bot = mb.vert(c + Z * r * sz), mb.vert(c - Z * r * sz)
    rows = []
    for i in range(1, rings):
        phi = math.pi * i / rings
        rows.append([mb.vert(c + Vector((math.sin(phi) * math.cos(TAU * j / segs) * r,
                                         math.sin(phi) * math.sin(TAU * j / segs) * r,
                                         math.cos(phi) * r * sz))) for j in range(segs)])
    for j in range(segs):
        k = (j + 1) % segs
        u0, u1 = j / segs, (j + 1) / segs
        mb.face((top, rows[0][j], rows[0][k]), [((u0 + u1) / 2, 1.0), (u0, 1 - 1 / rings), (u1, 1 - 1 / rings)])
        for i in range(rings - 2):
            v0, v1 = 1 - (i + 1) / rings, 1 - (i + 2) / rings
            mb.face((rows[i][j], rows[i + 1][j], rows[i + 1][k], rows[i][k]), [(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
        mb.face((rows[-1][j], bot, rows[-1][k]), [(u0, 1 / rings), ((u0 + u1) / 2, 0.0), (u1, 1 / rings)])


def cylinder(mb, base, r0, r1, h, segs, cap_top=True, cap_bot=False, tile=0.3, smooth=True):
    ring = [Vector((math.cos(TAU * j / segs), math.sin(TAU * j / segs), 0.0)) for j in range(segs)]
    bot = [mb.vert(base + d * r0) for d in ring]
    top = [mb.vert(base + d * r1 + Z * h) for d in ring]
    circ = TAU * max(r0, r1) / tile
    for j in range(segs):
        k = (j + 1) % segs
        u0, u1 = j / segs * circ, (j + 1) / segs * circ
        mb.face((bot[j], bot[k], top[k], top[j]), [(u0, 0.0), (u1, 0.0), (u1, h / tile), (u0, h / tile)], smooth=smooth)
    for cap, ring_ids, z, r in ((cap_top, top, h, r1), (cap_bot, bot, 0.0, r0)):
        if not cap:
            continue
        c = mb.vert(base + Z * z)
        for j in range(segs):
            k = (j + 1) % segs
            uv = [(0.5 + ring[j].x * r / tile, 0.5 + ring[j].y * r / tile),
                  (0.5 + ring[k].x * r / tile, 0.5 + ring[k].y * r / tile), (0.5, 0.5)]
            if ring_ids is top:
                mb.face((top[j], top[k], c), uv, smooth=False)
            else:
                mb.face((bot[k], bot[j], c), [uv[1], uv[0], uv[2]], smooth=False)


def tube(mb, p0, p1, r, segs=8):
    d = (p1 - p0).normalized()
    a = d.orthogonal().normalized()
    b = d.cross(a)
    ring = [a * math.cos(TAU * j / segs) + b * math.sin(TAU * j / segs) for j in range(segs)]
    r0 = [mb.vert(p0 + v * r) for v in ring]
    r1 = [mb.vert(p1 + v * r) for v in ring]
    for j in range(segs):
        k = (j + 1) % segs
        mb.face((r0[j], r0[k], r1[k], r1[j]), [(j / segs, 0), ((j + 1) / segs, 0), ((j + 1) / segs, 1), (j / segs, 1)])


def strip(mb, pts, widths, half):
    """Ribbon strip; front and back get their own vertices so each side shades correctly."""
    n = len(pts)
    for back in (False, True):
        left = [mb.vert(p - w * half) for p, w in zip(pts, widths)]
        right = [mb.vert(p + w * half) for p, w in zip(pts, widths)]
        for i in range(n - 1):
            quad = [left[i], right[i], right[i + 1], left[i + 1]]
            uv = [(0, i / (n - 1)), (1, i / (n - 1)), (1, (i + 1) / (n - 1)), (0, (i + 1) / (n - 1))]
            if back:
                quad.reverse()
                uv.reverse()
            mb.face(quad, uv)


def add_bmesh(mb, bm, mat, tile):
    bm.verts.index_update()
    bm.normal_update()
    ids = [mb.vert(mat @ v.co) for v in bm.verts]
    for f in bm.faces:
        ax = max(range(3), key=lambda k: abs(f.normal[k]))
        uv = []
        for v in f.verts:
            a, b = [(v.co.y, v.co.z), (v.co.x, v.co.z), (v.co.x, v.co.y)][ax]
            uv.append((a / tile + 0.5, b / tile + 0.5))
        mb.face([ids[v.index] for v in f.verts], uv, smooth=False)
    bm.free()


def box_bm(sx, sy, sz, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz + sz * 0.5))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect='EDGES')
    return bm


# ---------------------------------------------------------------- presents

GIFTS = [
    # kind, dims (x,y,z | radius,height), ring radius, angle (0 = +X front), yaw, paper, ribbon, bow
    ("box", (0.30, 0.26, 0.24), 0.62, -36, 18, "gold", "red", True),
    ("box", (0.20, 0.18, 0.30), 0.46, -8, -12, "red", "gold", True),
    ("cyl", (0.085, 0.16), 0.50, 16, 0, "red", "gold", True),
    ("box", (0.24, 0.22, 0.20), 0.36, 36, 25, "gold", "red", True),
    ("box", (0.42, 0.18, 0.08), 0.74, 30, 72, "gold", "red", False),
    ("box", (0.22, 0.22, 0.22), 0.62, 60, -15, "gold", "red", True),
    ("box", (0.20, 0.20, 0.18), 0.42, 82, 30, "red", "gold", True),
    ("box", (0.16, 0.14, 0.07), 0.88, 68, 10, "gold", "red", False),
    ("box", (0.18, 0.18, 0.28), 0.46, 112, -20, "gold", "red", True),
    ("box", (0.28, 0.22, 0.22), 0.56, 145, 20, "red", "gold", True),
    ("box", (0.24, 0.24, 0.18), 0.58, 195, 35, "gold", "red", True),
    ("cyl", (0.07, 0.12), 0.62, 240, 0, "red", "gold", True),
    ("box", (0.20, 0.26, 0.16), 0.60, 288, -25, "red", "gold", True),
    ("box", (0.26, 0.20, 0.20), 0.50, 326, 10, "gold", "red", True),
]
STACKED = [  # base gift index, dims, extra yaw, paper, ribbon, bow
    (4, (0.13, 0.12, 0.10), 20, "gold", "red", True),
    (9, (0.14, 0.14, 0.10), -10, "gold", "red", True),
]


def footprint(g, pad=0.0):
    c, s = math.cos(g["yaw"]), math.sin(g["yaw"])
    hx, hy = g["sx"] / 2 + pad, g["sy"] / 2 + pad
    return [(g["cx"] + c * dx - s * dy, g["cy"] + s * dx + c * dy)
            for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]


def overlap(a, b):
    for poly in (a, b):
        for i in range(4):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % 4]
            nx, ny = y2 - y1, x1 - x2
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def layout_gifts():
    items = []
    for kind, dims, ring_r, ang, yaw, paper, ribbon, bow in GIFTS:
        if kind == "box":
            sx, sy, sz = dims
        else:
            sx = sy = dims[0] * 2 + 0.012
            sz = dims[1] + 0.004
        a = math.radians(ang)
        items.append(dict(kind=kind, dims=dims, cx=ring_r * math.cos(a), cy=ring_r * math.sin(a),
                          yaw=math.radians(yaw), sx=sx, sy=sy, sz=sz, z0=0.0,
                          paper=paper, ribbon=ribbon, bow=bow))
    for _ in range(800):
        moved = False
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if overlap(footprint(a, 0.012), footprint(b, 0.012)):
                    dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]
                    dl = math.hypot(dx, dy) or 1e-6
                    for g, sgn in ((a, -1), (b, 1)):
                        g["cx"] += sgn * dx / dl * 0.006
                        g["cy"] += sgn * dy / dl * 0.006
                    moved = True
            min_r = 0.08 + 0.5 * math.hypot(a["sx"], a["sy"])
            rr = math.hypot(a["cx"], a["cy"])
            if rr < min_r:
                a["cx"] *= min_r / rr
                a["cy"] *= min_r / rr
                moved = True
        if not moved:
            break
    for base_i, dims, yaw, paper, ribbon, bow in STACKED:
        base = items[base_i]
        items.append(dict(kind="box", dims=dims, cx=base["cx"], cy=base["cy"],
                          yaw=base["yaw"] + math.radians(yaw), sx=dims[0], sy=dims[1], sz=dims[2],
                          z0=base["z0"] + base["sz"], paper=paper, ribbon=ribbon, bow=bow))
    for g in items:
        g["b"] = max(0.02, min(0.04, 0.13 * min(g["sx"], g["sy"])))
        g["z1"] = g["z0"] + g["sz"] + (2.4 * g["b"] if g["bow"] else 0.01)
    return items


def bow(mb, top, yaw, b):
    knot = top + Z * (b * 0.2)
    loops = [(0.0, 1.0), (math.pi, 1.0)]
    if b > 0.024:
        loops += [(math.pi / 2, 0.7), (-math.pi / 2, 0.7)]
    for ang, s in loops:
        d = Vector((math.cos(yaw + ang), math.sin(yaw + ang), 0.0))
        tilt = Matrix.Rotation(math.radians(rng.uniform(-15, 15)), 3, d)
        up, w = tilt @ Z, tilt @ Z.cross(d).normalized()
        a, c = 2.6 * b * s, 1.8 * b * s
        pts = []
        for i in range(17):
            t = i / 16
            p = knot + d * (a * math.sin(math.pi * t) ** 2) \
                + up * (c * (0.5 * math.sin(TAU * t) + 0.55 * math.sin(math.pi * t) ** 2))
            p.z = max(p.z, top.z + 0.002)
            pts.append(p)
        strip(mb, pts, [w] * len(pts), b * 0.5)
    for s in (-1, 1):
        d = Vector((math.cos(yaw + math.pi * 0.5 + s * 0.55), math.sin(yaw + math.pi * 0.5 + s * 0.55), 0.0))
        pts = [knot + d * (2.4 * b * i / 8) - Z * ((knot.z - top.z - 0.002) * min(1.0, i / 3)) for i in range(9)]
        strip(mb, pts, [Z.cross(d)] * len(pts), b * 0.45)
    sphere(mb, knot, b * 0.55, 10, 6, sz=0.7)


def build_gift(g, mbs):
    paper = mbs["xmas_gift_paper_" + g["paper"]]
    ribbon = mbs["xmas_gift_ribbon_" + g["ribbon"]]
    sx, sy, sz, b = g["sx"], g["sy"], g["sz"], g["b"]
    M = Matrix.Translation((g["cx"], g["cy"], g["z0"])) @ Matrix.Rotation(g["yaw"], 4, "Z")
    if g["kind"] == "box":
        add_bmesh(paper, box_bm(sx, sy, sz, 0.006), M, 0.35)
    else:
        r, h = g["dims"]
        base = Vector((g["cx"], g["cy"], g["z0"]))
        cylinder(paper, base, r, r, h - 0.03, 24, cap_top=False, cap_bot=True, tile=0.35)
        cylinder(paper, base + Z * (h - 0.034), r + 0.006, r + 0.006, 0.038, 24, cap_top=True, cap_bot=True, tile=0.35)
    # second band sits 0.8 mm proud of the first so the crossing never z-fights
    for e, dims in ((0.0025, (sx + 0.005, b, sz + 0.005)), (0.0033, (b, sy + 0.0066, sz + 0.0066))):
        add_bmesh(ribbon, box_bm(*dims), M @ Matrix.Translation((0, 0, -e)), 1.0)
    if g["bow"]:
        top = M @ Vector((0.0, 0.0, sz + 0.0034))
        bow(ribbon, top, g["yaw"] + rng.choice((0.0, math.pi / 2)) + math.radians(rng.uniform(-20, 20)), b)


def inside_gift(p, gifts, pad=0.03):
    for g in gifts:
        c, s = math.cos(-g["yaw"]), math.sin(-g["yaw"])
        dx, dy = p.x - g["cx"], p.y - g["cy"]
        lx, ly = dx * c - dy * s, dx * s + dy * c
        if abs(lx) < g["sx"] / 2 + pad and abs(ly) < g["sy"] / 2 + pad and p.z < g["z1"] + pad:
            return True
    return False


# ---------------------------------------------------------------- tree

def fol_normal(p, up):
    """Outward + upward normals make thousands of cards light as one soft cone."""
    r = Vector((p.x, p.y, 0.0))
    if r.length < 0.04:
        return (Z + up * 0.5).normalized()
    return (r.normalized() + Z * 0.5 + up * 0.25).normalized()


def branch_curve(start, d, length, elev, droop):
    ce, se = math.cos(elev), math.sin(elev)

    def f(u):
        return start + d * (length * u * ce) + Z * (length * (u * se - droop * u * u + 0.4 * droop * u ** 4))
    return f


def card(mb, curve, width, variant, roof, roll, rows, mirror, side_hint=None):
    """Inverted-V needle card along curve(u); both faces share the outward normal."""
    v_mid, span = (0.75, 0.243) if variant == 0 else (0.25, 0.243)
    pts = [curve(i / (rows - 1)) for i in range(rows)]
    rings = []
    for i, c in enumerate(pts):
        u = i / (rows - 1)
        tng = (pts[min(i + 1, rows - 1)] - pts[max(i - 1, 0)]).normalized()
        side = tng.cross(Z)
        if side.length < 1e-3:
            side = side_hint.copy()
        side.normalize()
        up = side.cross(tng).normalized()
        cs, sn = math.cos(roll), math.sin(roll)
        side, up = side * cs + up * sn, up * cs - side * sn
        frac = (0.62 + 0.38 * smoothstep(0.0, 0.3, u)) * (1.0 - 0.18 * smoothstep(0.75, 1.0, u))
        w = width * 0.5 * frac
        drop = up * (w * math.sin(roof))
        left, right = c - side * (w * math.cos(roof)) - drop, c + side * (w * math.cos(roof)) - drop
        vl, vr = v_mid - span * frac, v_mid + span * frac
        if mirror:
            vl, vr = vr, vl
        uu = 0.008 + u * 0.984
        rings.append(((left, c, right), ((uu, vl), (uu, v_mid), (uu, vr)), up))
    for back in (False, True):
        ids = [[mb.vert(p) for p in ring[0]] for ring in rings]
        for i in range(rows - 1):
            for a, b in ((0, 1), (1, 2)):
                quad = [(i, a), (i, b), (i + 1, b), (i + 1, a)]
                if back:
                    quad.reverse()
                mb.face([ids[r][k] for r, k in quad], [rings[r][1][k] for r, k in quad],
                        [fol_normal(rings[r][0][k], rings[r][2]) for r, k in quad])


def fitted_curve(start, d, length, elev, droop, gifts):
    """Lift or shorten a low branch until it no longer pokes into a present."""
    for _ in range(8):
        curve = branch_curve(start, d, length, elev, droop)
        if not any(inside_gift(curve(u), gifts) for u in (0.5, 0.75, 1.0)):
            return curve, length
        elev += math.radians(6)
        droop *= 0.7
        length *= 0.9
    return branch_curve(start, d, length, elev, droop), length


def build_foliage(mb, gifts):
    h = H0
    whorls = []
    while h < H_TIP - 0.16:
        whorls.append(h)
        h += lerp(0.115, 0.07, (h - H0) / (H_TIP - H0)) * rng.uniform(0.85, 1.15)
    cards = 0
    for h in whorls:
        t = (h - H0) / (H_TIP - H0)
        n = max(3, int(round(lerp(9, 4, t) + rng.uniform(-1, 1))))
        a0 = rng.uniform(0, TAU)
        for i in range(n):
            az = a0 + (i + rng.uniform(-0.3, 0.3)) * TAU / n
            d = Vector((math.cos(az), math.sin(az), 0.0))
            elev = math.radians(lerp(-3, 24, t) + rng.uniform(-5, 5))
            droop = lerp(0.22, 0.05, t) * rng.uniform(0.8, 1.2)
            length = max(0.08, crown_radius(h) * rng.uniform(0.95, 1.10) / max(0.5, math.cos(elev)))
            start = d * trunk_radius(h) + Z * h
            curve, length = fitted_curve(start, d, length, elev, droop, gifts)
            card(mb, curve, 0.52 * length, 0 if rng.random() < 0.75 else 1, math.radians(rng.uniform(22, 34)),
                 math.radians(rng.uniform(-10, 10)), 4 if length > 0.25 else 3, rng.random() < 0.5)
            cards += 1
            if length > 0.22:
                s = rng.choice((-1, 1))
                d2 = Matrix.Rotation(s * math.radians(rng.uniform(25, 40)), 3, Z) @ d
                l2 = length * rng.uniform(0.45, 0.6)
                c2, l2 = fitted_curve(curve(rng.uniform(0.3, 0.45)) - Z * 0.015, d2, l2,
                                      elev - math.radians(6), droop * 1.3, gifts)
                card(mb, c2, 0.52 * l2, 0, math.radians(rng.uniform(22, 34)),
                     math.radians(rng.uniform(-12, 12)), 3, rng.random() < 0.5)
                cards += 1

    for count, rmin, rmax, variant in ((660, 0.95, 1.08, 0), (230, 0.45, 0.80, 1)):
        placed = 0
        while placed < count:
            h = rng.uniform(H0 - 0.02, H_TIP - 0.06)
            R = crown_radius(h)
            if rng.random() > 0.35 + 0.65 * R / R_MAX:  # the crown top is seen more than its area suggests
                continue
            az = rng.uniform(0, TAU)
            out = Vector((math.cos(az), math.sin(az), 0.0))
            d = Matrix.Rotation(math.radians(rng.uniform(-30, 30)), 3, Z) @ out
            pitch = math.radians(rng.uniform(-38, 8))
            length = min(0.30, max(0.08, 0.36 * R + 0.05)) * rng.uniform(0.8, 1.15)
            tip = out * (R * rng.uniform(rmin, rmax)) + Z * h
            start = tip - Vector((d.x * math.cos(pitch), d.y * math.cos(pitch), math.sin(pitch))) * length
            if Vector((start.x, start.y)).length < trunk_radius(start.z) + 0.01:
                continue
            curve, length = fitted_curve(start, d, length, pitch, 0.12, gifts)
            card(mb, curve, 0.52 * length, variant, math.radians(rng.uniform(20, 34)),
                 math.radians(rng.uniform(-25, 25)), 3, rng.random() < 0.5)
            placed += 1
            cards += 1

    leader_base = Z * (H_TIP - 0.30)
    for side in (Vector((1, 0, 0)), Vector((0, 1, 0))):
        card(mb, lambda u: leader_base + Z * (0.33 * u), 0.11, 0, 0.0, 0.0, 3, False, side_hint=side)
        cards += 1
    for i in range(11):
        az = TAU * i / 11 + rng.uniform(-0.25, 0.25)
        d = Vector((math.cos(az), math.sin(az), 0.0))
        h = rng.uniform(H_TIP - 0.45, H_TIP - 0.08)
        curve = branch_curve(d * 0.01 + Z * h, d, rng.uniform(0.11, 0.18), math.radians(rng.uniform(40, 62)), 0.05)
        card(mb, curve, 0.085, 0, math.radians(20), 0.0, 3, rng.random() < 0.5)
        cards += 1
    return cards


def build_core(mb):
    """Dark opaque cone inside the cards so the crown never reads as see-through."""
    rings, segs = 22, 20
    z0, z1 = H0 - 0.06, H_TIP - 0.38
    ids = []
    for i in range(rings + 1):
        z = lerp(z0, z1, i / rings)
        row = []
        for j in range(segs):
            th = TAU * j / segs
            n = noise.noise(Vector((math.cos(th) * 1.3, math.sin(th) * 1.3, z * 2.7)))
            r = max(0.02, 0.48 * crown_radius(z)) * (1.0 + 0.12 * n)
            row.append(mb.vert((r * math.cos(th), r * math.sin(th), z)))
        ids.append(row)
    for i in range(rings):
        za, zb = lerp(z0, z1, i / rings) / 0.45, lerp(z0, z1, (i + 1) / rings) / 0.45
        for j in range(segs):
            k = (j + 1) % segs
            u0, u1 = 3 * j / segs, 3 * (j + 1) / segs
            mb.face((ids[i][j], ids[i][k], ids[i + 1][k], ids[i + 1][j]), [(u0, za), (u1, za), (u1, zb), (u0, zb)])
    apex, bottom = mb.vert((0, 0, z1 + 0.1)), mb.vert((0, 0, z0))
    for j in range(segs):
        k = (j + 1) % segs
        mb.face((ids[-1][j], ids[-1][k], apex), [(0, 0), (1, 0), (0.5, 1)])
        mb.face((ids[0][k], ids[0][j], bottom), [(0, 0), (1, 0), (0.5, 1)])


def build_trunk(mb):
    top = H_TIP - 0.22
    cylinder(mb, Vector((0, 0, 0)), trunk_radius(0.0), trunk_radius(top), top, 10, cap_top=False, cap_bot=True, tile=0.4)


def build_baubles(mb_red, mb_gold):
    pts = []
    tries = 0
    while len(pts) < 40 and tries < 50000:
        tries += 1
        h = rng.uniform(H0 + 0.08, H_TIP - 0.32)
        R = crown_radius(h)
        if rng.random() > R / R_MAX:
            continue
        az = rng.uniform(0, TAU)
        r = R * rng.uniform(0.92, 1.0)
        p = Vector((r * math.cos(az), r * math.sin(az), h - 0.03))
        if all((p - q).length >= 0.25 for q in pts):
            pts.append(p)
    colours = ["red", "gold"] * (len(pts) // 2 + 1)
    rng.shuffle(colours)
    for p, colour in zip(pts, colours):
        rad = lerp(0.056, 0.042, (p.z - H0) / (H_TIP - H0)) * rng.uniform(0.92, 1.08)
        sphere(mb_red if colour == "red" else mb_gold, p, rad, 12, 8)
        cylinder(mb_gold, p + Z * (rad * 0.86), rad * 0.26, rad * 0.24, rad * 0.24, 8, cap_top=True)
    return len(pts)


def build_lights(mb, count=92, turns=7.5):
    """Evenly spaced along a spiral, like a real light string, then jittered in and out."""
    samples = []
    for i in range(2001):
        s = i / 2000
        h = lerp(H0 + 0.04, H_TIP - 0.22, s)
        r = crown_radius(h) * 0.86
        samples.append(Vector((r * math.cos(s * turns * TAU), r * math.sin(s * turns * TAU), h)))
    cum = [0.0]
    for a, b in zip(samples, samples[1:]):
        cum.append(cum[-1] + (b - a).length)
    for k in range(count):
        p = samples[min(len(samples) - 1, bisect.bisect_left(cum, (k + 0.5) / count * cum[-1]))]
        f = rng.uniform(0.82, 1.08)
        sphere(mb, Vector((p.x * f, p.y * f, p.z + rng.uniform(-0.03, 0.03))), 0.011, 6, 4)
    return count


def build_star(mb_frame, mb_bulb):
    ro, ri = 0.19, 0.081
    zc = H_TIP + 0.005 + ro * math.cos(math.radians(36))
    pts = []
    for k in range(10):
        a = math.radians(90 + 36 * k)
        r = ro if k % 2 == 0 else ri
        pts.append(Vector((0.0, r * math.cos(a), zc + r * math.sin(a))))  # faces +X, the model's forward
    for k in range(10):
        a, b = pts[k], pts[(k + 1) % 10]
        tube(mb_frame, a, b, 0.010, 8)
        sphere(mb_bulb, a, 0.019 if k % 2 == 0 else 0.016, 10, 6)
        sphere(mb_bulb, (a + b) * 0.5, 0.013, 8, 5)
    cylinder(mb_frame, Vector((0, 0, H_TIP - 0.12)), 0.009, 0.009, zc - ri - (H_TIP - 0.12), 8, cap_top=False)


def build_phys(coll, gifts):
    pts = []
    for g in gifts:
        for x, y in footprint(g):
            for z in (g["z0"], g["z0"] + g["sz"]):
                pts.append((x, y, z))
    for k in range(16):
        th = TAU * k / 16
        pts.append((0.62 * math.cos(th), 0.62 * math.sin(th), 0.25))
        pts.append((0.62 * math.cos(th), 0.62 * math.sin(th), 0.0))
    for k in range(6):
        th = TAU * k / 6
        pts.append((0.05 * math.cos(th), 0.05 * math.sin(th), H_TIP + 0.38))
    bm = kit.convex_hull([FRONT @ Vector(p) for p in pts])
    me = bpy.data.meshes.new("christmas_tree_phys")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("christmas_tree_phys", me)
    coll.objects.link(ob)
    return ob


# ---------------------------------------------------------------- materials

# Blender material -> object, vmat, roughness, metalness, preview emission: the vmats are written from these rows.
MATERIALS = {
    "xmas_branch": ("tree_branches", "branch", 0.8, 0.0, 0.0),
    "xmas_core": ("tree_core", "core", 0.9, 0.0, 0.0),
    "xmas_bark": ("tree_trunk", "bark", 0.9, 0.0, 0.0),
    "xmas_bauble_red": ("baubles_red", "bauble_red", 0.12, 0.45, 0.0),
    "xmas_bauble_gold": ("baubles_gold", "bauble_gold", 0.24, 0.85, 0.0),
    "xmas_light_red": ("fairy_lights", "light_red", 0.3, 0.0, 5.0),
    "xmas_star_frame": ("star_frame", "star_frame", 0.3, 1.0, 0.0),
    "xmas_star_bulb": ("star_bulbs", "star_bulb", 0.3, 0.0, 7.0),
    "xmas_gift_paper_gold": ("gifts_paper_gold", "gift_paper_gold", 0.45, 0.3, 0.0),
    "xmas_gift_paper_red": ("gifts_paper_red", "gift_paper_red", 0.6, 0.0, 0.0),
    "xmas_gift_ribbon_red": ("gifts_ribbon_red", "gift_ribbon_red", 0.32, 0.15, 0.0),
    "xmas_gift_ribbon_gold": ("gifts_ribbon_gold", "gift_ribbon_gold", 0.3, 0.7, 0.0),
}
VMAT_EXTRA = {
    "branch": {"comment": "Christmas tree needles. Cards are already double sided in the mesh, so no F_RENDER_BACKFACES.",
               "alpha_test": (0.35, f"{MAT_REL}/branch_trans.png"), "normal": f"{MAT_REL}/branch_normal.png"},
    "core": {"comment": "Christmas tree: opaque inner cone that keeps the crown from reading as see-through."},
    "light_red": {"comment": "Fairy-light bulbs. Self-illum setup mirrors stock models/generic/lamp_kit_01/bulb_01_glow_white_100.",
                  "self_illum": (4.0, (1.0, 0.14, 0.09))},
    "star_bulb": {"self_illum": (6.0, (1.0, 0.86, 0.6))},
}


def tex(tex_dir, name, non_color=False):
    img = bpy.data.images.load(os.path.join(tex_dir, name), check_existing=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def material(tex_dir, name, color, rough, metal=0.0, emit=0.0, normal=None, alpha_clip=None):
    m = bpy.data.materials.new(name)
    nt, bsdf = kit.principled(m)
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = tex(tex_dir, color)
    t.location = (-600, 300)
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        nt.links.new(t.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emit
    if normal:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = tex(tex_dir, normal, True)
        tn.location = (-600, -150)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-300, -150)
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if alpha_clip is not None:
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = alpha_clip
        gt.location = (-300, 100)
        nt.links.new(t.outputs["Alpha"], gt.inputs[0])
        nt.links.new(gt.outputs["Value"], bsdf.inputs["Alpha"])
    return m


def make_materials(tex_dir):
    mats = {}
    for name, (_, vmat, rough, metal, emit) in MATERIALS.items():
        extra = {"normal": "branch_normal.png", "alpha_clip": 0.35} if vmat == "branch" else {}
        mats[name] = material(tex_dir, name, f"{vmat}_color.png", rough, metal, emit, **extra)
    return mats


# ---------------------------------------------------------------- scene, export, preview

def new_collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def setup_preview():
    sc = kit.setup_render((0.085, 0.08, 0.105), 48, (640, 1040))
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 64
    coll = new_collection("preview")
    floor_me = bpy.data.meshes.new("preview_floor")
    floor_me.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
    fm = bpy.data.materials.new("preview_floor")
    _, fb = kit.principled(fm)
    fb.inputs["Base Color"].default_value = (0.11, 0.10, 0.125, 1.0)
    fb.inputs["Roughness"].default_value = 0.85
    floor_me.materials.append(fm)
    coll.objects.link(bpy.data.objects.new("preview_floor", floor_me))

    cams = {}
    for name, loc, target in (("cam_front", (4.7, 0.0, 1.38), (0, 0, 1.40)),
                              ("cam_three_quarter", (3.3, -2.7, 2.35), (0, 0, 1.15))):
        cd = bpy.data.cameras.new(name)
        cd.lens, cd.sensor_fit, cd.sensor_height = 37, "VERTICAL", 24
        ob = bpy.data.objects.new(name, cd)
        ob.location = FRONT @ Vector(loc)
        kit.look_at(ob, target)
        coll.objects.link(ob)
        cams[name] = ob
    sc.camera = cams["cam_front"]

    sun = bpy.data.lights.new("preview_sun", "SUN")
    sun.energy, sun.angle = 3.0, math.radians(4)
    so = bpy.data.objects.new("preview_sun", sun)
    az, el = math.radians(35), math.radians(42)
    so.rotation_euler = (-(FRONT @ Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))))) \
        .to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(so)
    fill = bpy.data.lights.new("preview_fill", "AREA")
    fill.energy, fill.size = 350.0, 3.0
    fo = bpy.data.objects.new("preview_fill", fill)
    fo.location = FRONT @ Vector((2.5, -3.0, 2.2))
    kit.look_at(fo, (0, 0, 1.2))
    coll.objects.link(fo)
    return cams


def export_fbx(path, objects):
    bpy.context.view_layer.update()
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE", global_scale=1.0,
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True, mesh_smooth_type="OFF",
        use_tspace=False, use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False)


def main():
    A = kit.cli(__doc__)
    addon = lambda rel: os.path.join(A.addon_root, *rel.split("/"))
    kit.clear_scene()

    coll_tree, coll_phys = new_collection("christmas_tree"), new_collection("physics")
    mats = make_materials(addon(MAT_REL))
    mbs = {name: MB() for name in mats}

    gifts = layout_gifts()
    for g in gifts:
        build_gift(g, mbs)
    build_trunk(mbs["xmas_bark"])
    build_core(mbs["xmas_core"])
    n_cards = build_foliage(mbs["xmas_branch"], gifts)
    n_baubles = build_baubles(mbs["xmas_bauble_red"], mbs["xmas_bauble_gold"])
    n_lights = build_lights(mbs["xmas_light_red"])
    build_star(mbs["xmas_star_frame"], mbs["xmas_star_bulb"])

    objects = [mbs[k].build(MATERIALS[k][0], mats[k], coll_tree) for k in mats if mbs[k].faces]
    phys = build_phys(coll_phys, gifts)
    phys.display_type = "WIRE"
    coll_phys.hide_render = True
    cams = setup_preview()

    export_fbx(os.path.join(A.out, "christmas_tree.fbx"), objects)
    export_fbx(os.path.join(A.out, "christmas_tree_phys.fbx"), [phys])
    for _, vmat, rough, metal, _ in MATERIALS.values():
        kit.write_vmat(addon(f"{MAT_REL}/{vmat}.vmat"), f"{MAT_REL}/{vmat}_color.png", rough, metal,
                       **VMAT_EXTRA.get(vmat, {}))
    kit.write_vmdl(addon(VMDL), [
        kit.material_group([(name, f"{MAT_REL}/{row[1]}.vmat") for name, row in MATERIALS.items()]),
        kit.hulls([("christmas_tree_phys", A.out_rel + "christmas_tree_phys.fbx", "wood")], "", FBX_SCALE, 10.0),
        kit.render_mesh(A.out_rel + "christmas_tree.fbx", FBX_SCALE, name=None),
    ])

    tris = sum(sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob in objects)
    print(f"STATS cards={n_cards} baubles={n_baubles} lights={n_lights} gifts={len(gifts)} "
          f"objects={len(objects)} tris={tris} phys_verts={len(phys.data.vertices)}")
    lo, hi = kit.bounds(objects)
    print(f"BOUNDS min={kit.fmt(lo)} max={kit.fmt(hi)} m")

    kit.save_blend(os.path.join(A.out, "christmas_tree.blend"))
    if A.render:
        sc = bpy.context.scene
        for name, cam in cams.items():
            sc.camera = cam
            sc.render.filepath = os.path.join(A.render, f"preview_{name}.png")
            bpy.ops.render.render(write_still=True)
            print("RENDERED", sc.render.filepath)


main()
