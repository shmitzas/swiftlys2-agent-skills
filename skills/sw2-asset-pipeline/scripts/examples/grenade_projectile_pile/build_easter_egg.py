"""Builds an Easter egg throwable: the held model on the stock decoy frame, its projectile and a pickup pile (a nest of
eggs), with their hull DMXs, VMDLs, textures, VMATs and a Panorama killfeed icon.

Run:  blender -b --factory-startup --python build_easter_egg.py -- --addon-root <content/csgo_addons/<addon>>
          --out <addon>/rawmodels/holiday/easter_egg [--render <dir>] [--only shot,shot]
Geometry is Source model space in inches (1 Blender unit = 1 inch). Measured 2026-11: the decoy can the first-person
hand wraps spans z -2.499..1.973 on weapon_offset (hex caps r 1.0, waist r 0.735); the HE frag body fits a sphere of
r 1.634; the stock "thrown" sequences draw weapon_offset at 1.3x (HE) and 1.5x (decoy). All relief is geometry.
"""
import math
import os
import re
import sys

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

import source2_kit as kit

TAU = math.tau
MAT_REL = "materials/holiday/easter_egg"
ICON_REL = "panorama/images/icons/equipment/easter_egg.svg"
VMDL_HELD = "weapons/custom/holiday/easter_egg/easter_egg.vmdl"
VMDL_PROJ = "models/props/holiday/easter_egg_projectile.vmdl"
VMDL_PILE = "models/props/holiday/easter_egg_pile.vmdl"

# weapons/models/grenade/decoy/weapon_decoy.vmdl_c bones in -b DATA order (m_modelSkeleton); rotations all identity.
DECOY_BONES = [("weapon", -1, (0.0, 0.0, 0.0)), ("weapon_offset", 0, (0.0, 0.0, 0.0)),
               ("handle", 1, (0.275942, 0.371106, 2.866549)), ("pin", 1, (0.110538, -0.594566, 2.607471)),
               ("ring", 3, (-0.539, 0.000019, -0.000001)), ("ag1_hand_r", 1, (0.0, 0.0, 0.0))]
# Attachments as -d decompiles them (-b MDAT has quaternions), NmSkeleton and holsters (-b DATA), hull surface (-b RED2).
DECOY_ATTACHMENTS = [kit.attachment("weapon_holster_center", "weapon_offset", (0, 0, 0)),
                     kit.attachment("camera_inventory", "weapon_offset", (-7.327121, 7.667733, 2.254524),
                                    (13.373014, -46.767082, -0.859198)),
                     kit.attachment("decoy_particle", "weapon_offset", (0, 0, 2.006624))]
DECOY_NMSKEL = "animation/skeletons/weapons/decoy.vnmskel"
DECOY_HOLSTER = ("grenade0", "grenade1")
DECOY_SURFACE = "weaponflashbang"
PROP_BONES = [("root", -1, (0.0, 0.0, 0.0))]
BODY_CENTRE = (0.0, 0.0, -0.263)  # middle of the decoy can the first-person hand wraps, not its bbox
HE_BODY_D = 3.27
THROWN_SCALE = 1.3                # the HE "thrown" scale: keeps the item/HE ratio in flight

HELD_L = 1.2 * HE_BODY_D          # long axis on weapon_offset Z (the can axis), pointed end up
HELD_W = 0.72 * HELD_L
SHIFT = 0.08                      # widest point 0.08 L below the middle: the blunt end (Hugelschaffer egg)
PROJ_L = HELD_L * THROWN_SCALE
PILE_EGG_L = 1.6 * HELD_L         # bigger than held so the eggs read from across a room
SINK = 0.3                        # how far an egg presses into the straw it rests on
TOUCH = 0.06                      # allowed interpenetration between resting eggs, so contacts never show a gap


# ---------------------------------------------------------------- surfaces of revolution

def catmull_rom(points, per_seg=24):
    """Open uniform Catmull-Rom polyline through `points` (end tangents mirrored)."""
    p = np.asarray(points, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    t = np.linspace(0.0, 1.0, per_seg, endpoint=False)[:, None]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2 + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2][None])
    return np.vstack(out)


def arc_fraction(r, z):
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(r), np.diff(z)))])
    return s / s[-1], s[-1]


def resample_profile(r, z, rings):
    """rings + 1 points at equal arc length along an (r, z) polyline, both ends kept."""
    frac, _ = arc_fraction(r, z)
    t = np.linspace(0.0, 1.0, rings + 1)
    return np.interp(t, frac, r), np.interp(t, frac, z)


def ring_mesh(pole0, rings, pole1, v):
    """Closed mesh: pole0, rings (n x segs x 3) and pole1, each ring counter-clockwise about the pole0 -> pole1
    direction so faces wind outward. u runs once around every ring (seam vertices shared, only UVs split);
    v[k] belongs to pole0, the rings, then pole1."""
    n, segs = len(rings), len(rings[0])
    verts = [tuple(pole0)] + [tuple(p) for ring in rings for p in ring] + [tuple(pole1)]
    top = len(verts) - 1
    idx = lambda k, j: 1 + k * segs + (j % segs)
    faces, uvs = [], []
    for j in range(segs):
        u0, u1 = j / segs, (j + 1) / segs
        faces.append((0, idx(0, j + 1), idx(0, j)))
        uvs.append([((u0 + u1) / 2, v[0]), (u1, v[1]), (u0, v[1])])
        for k in range(n - 1):
            faces.append((idx(k, j), idx(k, j + 1), idx(k + 1, j + 1), idx(k + 1, j)))
            uvs.append([(u0, v[k + 1]), (u1, v[k + 1]), (u1, v[k + 2]), (u0, v[k + 2])])
        faces.append((idx(n - 1, j), idx(n - 1, j + 1), top))
        uvs.append([(u0, v[n]), (u1, v[n]), ((u0 + u1) / 2, v[n + 1])])
    return np.array(verts), faces, uvs


def revolve(r, z, segs, v=None):
    """Closed surface of revolution about +Z. The (r, z) profile runs bottom pole -> top pole with r = 0 at both
    ends, counter-clockwise in (r, z). v defaults to the arc fraction. Also returns each vertex's (theta, ring)
    so callers can displace before meshing."""
    n = len(r)
    v = arc_fraction(r, z)[0] if v is None else v
    th = np.arange(segs) * TAU / segs
    rings = [np.stack([r[k] * np.cos(th), r[k] * np.sin(th), np.full(segs, z[k])], axis=1) for k in range(1, n - 1)]
    verts, faces, uvs = ring_mesh((0.0, 0.0, z[0]), rings, (0.0, 0.0, z[-1]), v)
    theta = np.concatenate([[0.0], np.tile(th, n - 2), [0.0]])
    ring = np.concatenate([[0], np.repeat(np.arange(1, n - 1), segs), [n - 1]])
    return verts, faces, uvs, theta, ring


def remap_uvs(uvs, su=1.0, ou=0.0, sv=1.0, ov=0.0):
    return [[(u * su + ou, v * sv + ov) for u, v in face] for face in uvs]


def unit_egg(n=2001):
    z = np.linspace(-0.5, 0.5, n)
    r = np.sqrt(np.clip((1 - 4 * z * z) / (1 + 8 * SHIFT * z + 4 * SHIFT * SHIFT), 0.0, None))
    return r * (HELD_W / HELD_L / 2) / r.max(), z


R_UNIT, Z_UNIT = unit_egg()
S_FRAC, S_LEN = arc_fraction(R_UNIT, Z_UNIT)  # texture v is this arc fraction; S_LEN in egg lengths


# ---------------------------------------------------------------- textures

def tile_noise(rng, shape, beta, f_lo, f_hi):
    """Periodic (hence tileable) band-limited noise, zero mean and unit deviation; frequencies in cycles per tile."""
    h, w = shape
    spec = np.fft.fft2(rng.standard_normal((h, w)))
    fy, fx = np.meshgrid(np.fft.fftfreq(h) * h, np.fft.fftfreq(w) * w, indexing="ij")
    f = np.hypot(fx, fy)
    f[0, 0] = 1.0
    out = np.real(np.fft.ifft2(spec * f ** (-beta / 2.0) * (f >= f_lo) * (f <= f_hi)))
    return (out - out.mean()) / (out.std() + 1e-12)


def uv_grid(w, h, ss=1):
    """Sample-centre UVs of a w x h texture, ss samples per pixel edge. PNG row 0 is the top, i.e. SMD/Blender v = 1."""
    u = (np.arange(w * ss) + 0.5) / (w * ss)
    v = 1.0 - (np.arange(h * ss) + 0.5) / (h * ss)
    return np.meshgrid(u, v)


def downsample(img, ss):
    if ss == 1:
        return img
    h, w = img.shape[0] // ss, img.shape[1] // ss
    return img.reshape(h, ss, w, ss, *img.shape[2:]).mean(axis=(1, 3))


def atlas_tile(k, count, height, gutter=6):
    """Rows of atlas tile k (tiles stacked in v) and the v range a mesh maps onto: inside a gutter that only ever
    holds pole colour, so mip bleed between neighbouring tiles stays invisible."""
    y0, y1 = round(k * height / count), round((k + 1) * height / count)
    return y0, y1, 1.0 - (y1 - gutter) / height, 1.0 - (y0 + gutter) / height


SKY, PINK, MINT, LEMON = (128, 190, 240), (244, 150, 192), (136, 222, 182), (253, 222, 110)
LILAC, PEACH, CREAM, CORAL = (186, 156, 236), (252, 178, 136), (252, 246, 230), (246, 128, 128)

# Sizes in egg lengths, bands in arc fraction (0 = blunt pole); whole repeat counts hide the u seam, plain poles hide the pinch.
DESIGNS = [
    (SKY, [("stripe", 0.255, 0.315, LILAC), ("stripe", 0.425, 0.585, PINK), ("zigzag", 0.505, 0.040, 0.026, 9, LEMON),
           ("stripe", 0.410, 0.425, CREAM), ("stripe", 0.585, 0.600, CREAM), ("dots", 0.705, 0.030, 10, 0.0, CREAM)]),
    (LEMON, [("stripe", 0.43, 0.57, MINT), ("zigzag", 0.50, 0.036, 0.024, 8, PINK), ("dots", 0.30, 0.030, 11, 0.5, LILAC),
             ("stripe", 0.68, 0.72, SKY)]),
    (MINT, [("wave", 0.50, 0.035, 0.050, 6, PINK), ("dots", 0.32, 0.026, 12, 0.0, CREAM), ("dots", 0.68, 0.026, 10, 0.5, CREAM),
            ("stripe", 0.80, 0.83, LEMON), ("stripe", 0.17, 0.20, LEMON)]),
    (PINK, [("stripe", 0.56, 0.61, SKY), ("tri", 0.56, 0.075, 10, -1, SKY), ("dots", 0.36, 0.028, 11, 0.5, LEMON),
            ("stripe", 0.73, 0.77, MINT), ("stripe", 0.22, 0.26, MINT)]),
    (LILAC, [("zigzag", 0.47, 0.045, 0.030, 7, LEMON), ("dots", 0.62, 0.030, 9, 0.0, PINK), ("dots", 0.32, 0.030, 11, 0.5, PINK),
             ("stripe", 0.76, 0.80, CREAM)]),
    (PEACH, [("stripe", 0.40, 0.44, MINT), ("stripe", 0.58, 0.62, MINT), ("wave", 0.51, 0.025, 0.026, 8, SKY),
             ("dots", 0.27, 0.026, 12, 0.0, CORAL), ("dots", 0.74, 0.026, 9, 0.5, CORAL)]),
]


def band_mask(op, u, s, circ):
    kind = op[0]
    if kind == "stripe":
        return (s >= op[1]) & (s < op[2])
    if kind in ("zigzag", "wave"):
        _, s_mid, amp, thick, n, _ = op
        c_mid = TAU * np.interp(s_mid, S_FRAC, R_UNIT)  # at the band, not per row: rows near a pole have none
        if kind == "zigzag":
            centre = 4.0 * np.abs((n * u) % 1.0 - 0.5) - 1.0
            slope = amp * 4.0 * n / c_mid
        else:
            centre = np.sin(TAU * n * u)
            slope = amp * TAU * n * np.cos(TAU * n * u) / c_mid
        half = 0.5 * thick / S_LEN * np.sqrt(1.0 + slope * slope)  # constant stroke width across the slopes
        return np.abs(s - s_mid - amp / S_LEN * centre) < half
    if kind == "dots":
        _, s_mid, rad, n, phase, _ = op
        du = ((n * u + phase) % 1.0 - 0.5) / n
        return (du * circ) ** 2 + ((s - s_mid) * S_LEN) ** 2 < rad * rad  # round on the egg, not in UV space
    if kind == "tri":
        _, s_base, h, n, sign, _ = op
        reach = h / S_LEN * (1.0 - np.abs(2.0 * ((n * u) % 1.0) - 1.0))
        d = (s - s_base) * sign
        return (d >= 0) & (d < reach)
    raise ValueError(kind)


def paint_egg(width, height, design, seed, v_lo=0.0, v_hi=1.0, ss=3):
    base, ops = design
    u, v = uv_grid(width, height, ss)
    s = np.clip((v - v_lo) / (v_hi - v_lo), 0.0, 1.0)
    circ = TAU * np.interp(s, S_FRAC, R_UNIT)
    img = np.empty(u.shape + (3,), np.float32)
    img[:] = base
    for op in ops:
        img[band_mask(op, u, s, circ)] = op[-1]
    img = downsample(img, ss)
    rng = np.random.default_rng(seed)
    mottle = 0.014 * tile_noise(rng, (height, width), 2.0, 1, 10) + 0.006 * tile_noise(rng, (height, width), 0.6, 20, 160)
    return img * (1.0 + mottle[..., None])


def straw_texture(size, seed, strands=6500):
    """Tileable hay: strands mostly running around the nest (u), each shaded as a round stalk over a soft shadow."""
    rng = np.random.default_rng(seed)
    img = np.empty((size, size, 3), np.float32)
    img[:] = np.array((70, 52, 30), np.float32) * (1.0 + 0.18 * tile_noise(rng, (size, size), 1.5, 2, 60))[..., None]
    palette = np.array([(224, 188, 114), (238, 210, 144), (200, 156, 86), (176, 132, 70), (212, 178, 106), (156, 122, 72),
                        (190, 170, 110)], np.float32)
    for _ in range(strands):
        length, width = rng.uniform(50, 170), rng.uniform(2.2, 5.0)
        ang = rng.normal(0.0, 0.25) + (rng.uniform(-1.3, 1.3) if rng.random() < 0.15 else 0.0)
        cx, cy = rng.uniform(0, size, 2)
        col = palette[rng.integers(len(palette))] * rng.uniform(0.86, 1.08)
        ux, uy = math.cos(ang), math.sin(ang)
        ex, ey = abs(ux) * length / 2 + width + 2, abs(uy) * length / 2 + width + 2
        xs = np.arange(math.floor(cx - ex), math.ceil(cx + ex))
        ys = np.arange(math.floor(cy - ey), math.ceil(cy + ey))
        px, py = np.meshgrid(xs + 0.5 - cx, ys + 0.5 - cy)
        t = np.clip(px * ux + py * uy, -length / 2, length / 2)
        d = np.hypot(px - t * ux, py - t * uy)
        hw = width / 2 * np.sqrt(np.clip(1.0 - (2.0 * t / length) ** 8, 0.0, 1.0))
        block = np.ix_(ys % size, xs % size)
        shadow = np.clip((hw + 1.8 - np.hypot(px - t * ux - 0.8, py - t * uy - 1.1)) / 1.5, 0.0, 1.0)
        img[block] *= (1.0 - 0.28 * shadow)[..., None]
        a = np.clip((hw + 0.6 - d) / 1.2, 0.0, 1.0)[..., None]
        shade = (0.70 + 0.30 * np.sqrt(np.clip(1.0 - (d / np.maximum(hw, 0.3)) ** 2, 0.0, 1.0)))[..., None]
        img[block] = img[block] * (1.0 - a) + col * shade * a
    return img


def make_textures(mat_dir):
    os.makedirs(mat_dir, exist_ok=True)
    out = {k: os.path.join(mat_dir, f"{k}_color.png") for k in ("easter_egg", "easter_egg_pile", "easter_egg_nest")}
    # 2:1 because the held egg is ~2.3x around what it is long: square texels on the egg.
    kit.write_png(out["easter_egg"], paint_egg(1024, 512, DESIGNS[0], 1))
    atlas = np.zeros((2048, 512, 3), np.float32)
    for k, design in enumerate(DESIGNS):
        y0, y1, _, _ = atlas_tile(k, len(DESIGNS), 2048)
        g = 6 / (y1 - y0)  # the gutter in tile-local v: it paints as pole colour
        atlas[y0:y1] = paint_egg(512, y1 - y0, design, 10 + k, v_lo=g, v_hi=1.0 - g)
    kit.write_png(out["easter_egg_pile"], atlas)
    kit.write_png(out["easter_egg_nest"], straw_texture(1024, 3))
    return out


ROUGH = {"easter_egg": 0.36, "easter_egg_pile": 0.36, "easter_egg_nest": 0.92}
COMMENTS = {"easter_egg": "Painted Easter egg: pastel bands on revolution UVs, glossy-ish paint. Relief is geometry, so no normal map.",
            "easter_egg_pile": "Atlas of the pile's six egg designs, one tile per design stacked in v.",
            "easter_egg_nest": "Straw nest under the egg pile: tileable hay strands running around the nest."}


# ---------------------------------------------------------------- geometry

def egg_parts(length, segs, rings, v_lo=0.0, v_hi=1.0):
    r, z = resample_profile(R_UNIT, Z_UNIT, rings)
    verts, faces, uvs, _, _ = revolve(r * length, z * length, segs)
    return verts, faces, remap_uvs(uvs, sv=v_hi - v_lo, ov=v_lo)


def egg_frame(yaw, elev, roll):
    """Local Z (blunt -> pointed) at `elev` above the horizon, heading `yaw`; roll spins the pattern about the axis."""
    c, s = math.cos, math.sin
    rz = lambda a: np.array([[c(a), -s(a), 0.0], [s(a), c(a), 0.0], [0.0, 0.0, 1.0]])
    b = math.pi / 2 - elev
    ry = np.array([[c(b), 0.0, s(b)], [0.0, 1.0, 0.0], [-s(b), 0.0, c(b)]])
    return rz(yaw) @ ry @ rz(roll)


def inside_egg(points, centre, frame, length, tol):
    loc = (points - centre) @ frame
    zl, rl = loc[:, 2] / length, np.hypot(loc[:, 0], loc[:, 1]) / length
    return (np.abs(zl) < 0.5) & (rl < np.interp(zl, Z_UNIT, R_UNIT) - tol / length)


NEST_CTRL = [(17.4, 0.0), (19.8, 0.85), (21.0, 2.7), (20.7, 5.1), (19.1, 7.0), (16.8, 7.8), (14.8, 7.3), (13.3, 6.1),
             (11.6, 5.0), (8.0, 4.35), (4.0, 4.15), (0.0, 4.1)]
NEST_TILE = 12.0                  # inches of straw per texture repeat


def nest_profile(rings):
    """Bottom pole -> flat underside -> rounded rim -> bowl -> bowl-centre pole (counter-clockwise in (r, z))."""
    dense = catmull_rom(NEST_CTRL, 32)
    r, z = resample_profile(dense[:, 0], dense[:, 1], rings)
    return np.concatenate([[0.0, 9.0], r]), np.concatenate([[0.0, 0.0], z]), dense


def nest_mesh(segs=72, rings=24):
    r, z, dense = nest_profile(rings)
    arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(r), np.diff(z)))])
    verts, faces, uvs, theta, ring = revolve(r, z, segs, v=arc / NEST_TILE)
    uvs = remap_uvs(uvs, su=9.0)
    zz = verts[:, 2]
    w = np.where(zz < 0.05, 0.0, np.clip(0.35 + 0.65 * (zz - 4.0) / 3.5, 0.35, 1.0))  # flat underside, lumpy rim
    o1, o2 = Vector((3.1, 7.7, 1.3)), Vector((-5.2, 2.9, 8.1))
    rad = np.array([noise.noise(Vector(p) / 3.2 + o1) + 0.5 * noise.noise(Vector(p) / 1.4 + o2) for p in verts])
    lift = np.array([noise.noise(Vector(p) / 2.6 + o2) for p in verts])
    rim = np.clip((zz - 5.0) / 2.5, 0.0, 1.0) * (0.45 * np.sin(3 * theta + 0.7) + 0.25 * np.sin(7 * theta + 2.0))
    rr = np.hypot(verts[:, 0], verts[:, 1])
    scale = np.where(rr > 1e-6, (rr + 0.55 * w * rad) / np.maximum(rr, 1e-6), 1.0)
    verts[:, 0] *= scale
    verts[:, 1] *= scale
    verts[:, 2] = np.maximum(verts[:, 2] + w * (0.35 * lift) + rim, 0.0)
    flat = [all(verts[i, 2] < 0.05 for i in f) for f in faces]
    return kit.mesh_from("easter_egg_nest", verts, faces, uvs, flat), dense


def nest_top(dense):
    """Upper envelope z(rho) of the smooth nest profile: what a falling egg lands on."""
    grid = np.linspace(0.0, 22.0, 881)
    top = np.full_like(grid, 0.0)
    for (ra, za), (rb, zb) in zip(dense[:-1], dense[1:]):
        lo, hi = min(ra, rb), max(ra, rb)
        if hi - lo < 1e-9:
            continue
        m = (grid >= lo) & (grid <= hi)
        top[m] = np.maximum(top[m], za + (grid[m] - ra) / (rb - ra) * (zb - za))
    return lambda rho: np.interp(rho, grid, top, right=0.0)


def heap_plan():
    """(x, y, yaw, elev, roll, size jitter): a ring against the bowl wall running around it, two on the floor,
    four in the hollows, two above and one lying across the top. Dropped in this order."""
    rng = np.random.default_rng(17)
    rnd = lambda lo, hi: float(rng.uniform(lo, hi))
    plan = []
    for k in range(9):
        a = 0.25 + TAU * k / 9
        plan.append((10.6 * math.cos(a), 10.6 * math.sin(a), a + math.pi / 2 + rnd(-0.3, 0.3), rnd(-0.10, 0.15),
                     rnd(0, TAU), rnd(0.95, 1.05)))
    for a in (1.0, 1.0 + math.pi):
        plan.append((3.6 * math.cos(a), 3.6 * math.sin(a), a + rnd(-0.5, 0.5), rnd(0.0, 0.1), rnd(0, TAU), rnd(0.97, 1.03)))
    for k in range(4):
        a = 0.6 + TAU * k / 4
        plan.append((6.4 * math.cos(a), 6.4 * math.sin(a), a + rnd(-0.5, 0.5), rnd(0.15, 0.35), rnd(0, TAU), rnd(0.95, 1.05)))
    for a in (1.9, 1.9 + math.pi):
        plan.append((2.2 * math.cos(a), 2.2 * math.sin(a), a + 1.4, 0.35, rnd(0, TAU), 1.0))
    plan.append((0.3, -0.2, 2.2, 0.6, rnd(0, TAU), 1.03))
    return plan


VARIANT_ORDER = [0, 1, 2, 3, 4, 5, 0, 2, 4, 3, 5, 1, 5, 3, 0, 2, 4, 1]  # ring neighbours never repeat


def lower_until_contact(clear, z_from, z_to=-5.0, coarse=0.25, fine=0.02):
    """Last offset at which clear(z) still holds while lowering from z_from: the resting contact, to `fine`."""
    z = z_from
    for step in (coarse, fine):
        while z - step > z_to and clear(z - step):
            z -= step
    return z


def build_pile(top):
    """Drop each egg of the plan onto the straw and the eggs already placed; returns per-egg (centre, frame, L, variant)."""
    sv, sf, _ = egg_parts(1.0, 16, 12)
    placed = []
    for i, (x, y, yaw, elev, roll, jitter) in enumerate(heap_plan()):
        length = PILE_EGG_L * jitter
        frame = egg_frame(yaw, elev, roll)
        base = sv * length @ frame.T + np.array((x, y, 0.0))

        def clear(z):
            pts = base + (0.0, 0.0, z)
            if np.any(pts[:, 2] < top(np.hypot(pts[:, 0], pts[:, 1])) - SINK):
                return False
            for c, f, ln, wpts in placed:
                if np.any(inside_egg(pts, c, f, ln, TOUCH)) or np.any(inside_egg(wpts, np.array((x, y, z)), frame, length, TOUCH)):
                    return False
            return True

        z = lower_until_contact(clear, 45.0)
        placed.append((np.array((x, y, z)), frame, length, base + (0.0, 0.0, z)))
    return [(c, f, ln, VARIANT_ORDER[i]) for i, (c, f, ln, _) in enumerate(placed)]


# ---------------------------------------------------------------- killfeed icon (Panorama SVG)

def closed_curve(points):
    """Closed cubic Bezier through `points` (Catmull-Rom tangents)."""
    n = len(points)
    segs = []
    for k in range(n):
        p0, p1, p2, p3 = (np.asarray(points[(k + d) % n], float) for d in (-1, 0, 1, 2))
        segs.append((p1, p1 + (p2 - p0) / 6, p2 - (p3 - p1) / 6, p2))
    return segs


def polygon(points):
    """Closed polygon as straight cubics (Panorama icons here stick to M/C/Z)."""
    n = len(points)
    segs = []
    for k in range(n):
        a, b = np.asarray(points[k], float), np.asarray(points[(k + 1) % n], float)
        segs.append((a, a + (b - a) / 3, a + 2 * (b - a) / 3, b))
    return segs


def svg_d(subpaths):
    f = lambda p: f"{p[0]:.3f} {p[1]:.3f}"
    d = " ".join(f"M {f(s[0][0])} " + " ".join(f"C {f(a)} {f(b)} {f(c)}" for _, a, b, c in s) + " Z" for s in subpaths)
    if not re.fullmatch(r"[MCZ0-9.\- ]+", d):  # an icon with arcs drew nothing in game until rewritten as cubics
        raise SystemExit(f"icon path uses unexpected commands: {d[:80]}")
    return d


def write_svg(path, layers):
    """layers: [(subpaths, opacity)], each an even-odd path. Root width/height are mandatory and set the raster size."""
    out = []
    for subpaths, opacity in layers:
        op = "" if opacity >= 1.0 else f' fill-opacity="{opacity:.3f}"'
        out.append(f'<path fill-rule="evenodd" clip-rule="evenodd" d="{svg_d(subpaths)}" fill="white"{op}/>')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n'
                '<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">\n'
                + "\n".join(out) + "\n</svg>\n")


def icon_preview(path, layers, scale=8, ss=4):
    """Even-odd raster of the icon layers composited white-over-dark, upscaled for viewing."""
    res = 32 * ss
    ys, xs = np.mgrid[0:res, 0:res]
    px, py = (xs + 0.5) / ss, (ys + 0.5) / ss
    cover = np.zeros((32, 32))
    for subpaths, opacity in layers:
        inside = np.zeros_like(px, dtype=bool)
        for segs in subpaths:
            poly = []
            for p0, c1, c2, p3 in segs:
                for t in np.linspace(0, 1, 17)[:-1]:
                    u = 1 - t
                    poly.append(u ** 3 * p0 + 3 * u * u * t * c1 + 3 * u * t * t * c2 + t ** 3 * p3)
            for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
                inside ^= ((y0 > py) != (y1 > py)) & (px < (x1 - x0) * (py - y0) / ((y1 - y0) or 1e-12) + x0)
        a = opacity * inside.reshape(32, ss, 32, ss).mean(axis=(1, 3))
        cover = cover + a * (1 - cover)
    bg = np.array([38, 40, 46], np.float32)
    img = bg + (255 - bg) * cover[..., None]
    kit.write_png(path, np.repeat(np.repeat(img, scale, 0), scale, 1))


def icon_layers():
    """Egg silhouette (blunt end down) with a zigzag band and a row of dots cut out even-odd, like the decoy's slots."""
    zs = np.linspace(-0.5, 0.5, 400)
    rs = np.interp(zs, Z_UNIT, R_UNIT)
    size, cy = 28.0, 16.0
    right = np.stack([16.0 + rs * size, cy - zs * size], axis=1)
    left = np.stack([16.0 - rs * size, cy - zs * size], axis=1)[::-1]
    outline = np.vstack([right, left[1:-1]])
    seg = np.hypot(*np.diff(np.vstack([outline, outline[:1]]), axis=0).T)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    pick = [outline[np.searchsorted(arc, t) % len(outline)] for t in np.linspace(0, arc[-1], 28, endpoint=False)]
    egg = closed_curve(pick)

    def inset(margin):
        """Outline pulled in by `margin` px, as a convex polygon to clip the cut-outs against."""
        zc = np.linspace(-0.5, 0.5, 61)
        r_in = np.maximum(np.interp(zc, Z_UNIT, R_UNIT) * size - margin, 0.05)
        ok = np.abs(zc * size) < size / 2 - margin
        rr = np.stack([16.0 + r_in[ok], cy - zc[ok] * size], axis=1)
        ll = np.stack([16.0 - r_in[ok], cy - zc[ok] * size], axis=1)[::-1]
        return np.vstack([rr, ll])

    def clip(subject, clipper):
        """Sutherland-Hodgman: any polygon against a convex clipper (both counter-clockwise in screen space)."""
        out = list(subject)
        for a, b in zip(clipper, np.roll(clipper, -1, axis=0)):
            inp, out = out, []
            side = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            for p, q in zip(inp, inp[1:] + inp[:1]):
                sp, sq = side(p), side(q)
                if sq <= 0:
                    if sp > 0:
                        out.append(p + (q - p) * (sp / (sp - sq)))
                    out.append(q)
                elif sp <= 0:
                    out.append(p + (q - p) * (sp / (sp - sq)))
        return out

    clipper = inset(1.6)
    if np.cross(clipper[1] - clipper[0], clipper[2] - clipper[1]) > 0:
        clipper = clipper[::-1]
    teeth, y_band, amp, thick = 4, 18.3, 1.0, 2.6
    xs = np.linspace(3.0, 29.0, 2 * teeth + 1)
    upper = [np.array((x, y_band - thick / 2 - amp * (1 if k % 2 else -1))) for k, x in enumerate(xs)]
    band = upper + [p + np.array((0.0, thick)) for p in upper[::-1]]
    band = clip(band, clipper)
    dots = []
    for x in (11.2, 16.0, 20.8):
        a = np.linspace(0, TAU, 8, endpoint=False)
        dots.append(closed_curve([np.array((x + 1.15 * math.cos(t), 10.6 + 1.15 * math.sin(t))) for t in a]))
    stripe = clip([np.array((2.0, 23.0)), np.array((30.0, 23.0)), np.array((30.0, 24.0)), np.array((2.0, 24.0))], clipper)
    return [([egg, polygon(band), polygon(stripe)] + dots, 1.0)]


# ---------------------------------------------------------------- ModelDoc

def write_prop_vmdl(path, remaps, smd, hull_files, particle_origin=None):
    """One-bone prop. A projectile passes particle_origin: the client plays the decoy ground effect at
    `decoy_particle`, and the model needs a `thrown` sequence."""
    children = [kit.material_group(remaps), kit.render_mesh(smd)]
    if particle_origin is not None:
        children += [{"_class": "AttachmentList", "children": [kit.attachment("decoy_particle", "root", particle_origin)]},
                     kit.animations("thrown")]
    children += [kit.hulls(hull_files, ""), kit.skeleton(PROP_BONES)]
    kit.write_vmdl(path, children)


# ---------------------------------------------------------------- checks and preview

def gate(ob):
    me = ob.data
    me.calc_loop_triangles()
    co = np.array([tuple(v.co) for v in me.vertices])
    tri = np.array([tuple(t.vertices) for t in me.loop_triangles])
    vol = float(np.einsum("ij,ij->i", co[tri[:, 0]], np.cross(co[tri[:, 1]], co[tri[:, 2]])).sum() / 6.0)
    bm = bmesh.new()
    bm.from_mesh(me)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    if vol <= 0 or bad:
        raise SystemExit(f"GATE FAILED {ob.name}: volume={vol:.3f} non_manifold_edges={bad}")
    return vol


def prim_cylinder(name, r, z0, z1, segs, cx=0.0, cy=0.0, phase=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=z1 - z0,
                          matrix=Matrix.Translation((cx, cy, (z0 + z1) / 2)) @ Matrix.Rotation(phase, 4, "Z"))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def prim_box(name, lo, hi):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector([lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def prim_sphere(name, r, centre):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=r, matrix=Matrix.Translation(centre))
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def wire(ob, thickness):
    mod = ob.modifiers.new("wire", "WIREFRAME")
    mod.thickness, mod.use_replace = thickness, True


def camera(coll, name, loc, target, lens=50.0, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.clip_start, cd.clip_end = lens, 0.1, 5000.0
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    ob = bpy.data.objects.new(name, cd)
    ob.location = Vector(loc)
    kit.look_at(ob, target)
    coll.objects.link(ob)
    return ob


def area_lights(coll, centre, dist, energy):
    """Key/fill/rim; energy is the key's watts at `dist` Blender units (inches)."""
    for name, e, d in (("key", 1.0, (0.9, -0.6, 0.8)), ("fill", 0.35, (-0.8, -0.9, 0.2)), ("rim", 0.55, (-0.3, 1.0, 0.6))):
        ld = bpy.data.lights.new(f"{coll.name}_{name}", "AREA")
        ld.energy, ld.size = energy * e, dist * 0.6
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = Vector(centre) + Vector(d).normalized() * dist
        kit.look_at(lo, centre)
        coll.objects.link(lo)


COLLECTIONS = ("held", "projectile", "pile", "ref_decoy", "ref_he", "ref_he_thrown", "ref_player",
               "ghost", "floor", "rig_small", "rig_large", "cameras")


def new_scene():
    sc = kit.clear_scene(0.0254)
    colls = {k: bpy.data.collections.new(k) for k in COLLECTIONS}
    for k in COLLECTIONS:
        sc.collection.children.link(colls[k])  # flat: a hidden parent would hide its children in renders
    return colls


def setup_preview(colls, held, held_lo, held_hi, proj_d, pile_lo, pile_hi):
    """Reference props rebuilt from measured numbers only (no stock geometry), lights and the standard shots."""
    kit.setup_render((0.05, 0.055, 0.07), 64, (960, 640))
    c = colls
    red = kit.blender_material("ref_decoy", color=(0.85, 0.12, 0.08), rough=0.5)
    olive = kit.blender_material("ref_he", color=(0.22, 0.25, 0.14), rough=0.45, metal=0.3)
    wire_white = kit.blender_material("ref_wire", color=(0.9, 0.9, 0.9), rough=0.5, emit=1.5)
    grey = kit.blender_material("ref_player", color=(0.35, 0.37, 0.42), rough=0.8, alpha=0.55)
    floor = kit.blender_material("preview_floor", color=(0.10, 0.10, 0.12), rough=0.9)
    ghost = kit.blender_material("ghost_item", color=(1.0, 0.95, 0.85), rough=0.6, alpha=0.22)

    can = c["ref_decoy"]
    for name, r, z0, z1, segs in (("can_cap_low", 1.0, -2.4993, -1.54, 6), ("can_waist", 0.735, -1.54, 1.03, 32),
                                  ("can_cap_high", 1.0, 1.03, 1.973, 6), ("can_fuze", 0.38, 1.973, 2.96, 16)):
        kit.add_object(can, name, prim_cylinder(name, r, z0, z1, segs, phase=math.pi / 2), red)
    for name, axis, col in (("axis_x", 0, (1, 0.1, 0.1)), ("axis_y", 1, (0.1, 1, 0.1)), ("axis_z", 2, (0.2, 0.4, 1))):
        ob = kit.add_object(can, name, prim_cylinder(name, 0.03, 0.0, 3.2, 8), kit.blender_material(name, color=col, emit=2.0))
        ob.rotation_euler = ((0, math.pi / 2, 0), (-math.pi / 2, 0, 0), (0, 0, 0))[axis]
    for ob in held:
        g = kit.add_object(c["ghost"], ob.name + "_ghost", ob.data.copy(), None)
        g.data.materials.clear()
        g.data.materials.append(ghost)

    # HE: LSQ sphere of the frag body and the whole-model bounds (spoon, pin, ring), 6" to the side.
    he = c["ref_he"]
    kit.add_object(he, "he_body", prim_sphere("he_body", HE_BODY_D / 2, (0.106, 6.0, -0.488)), olive)
    box = kit.add_object(he, "he_bounds", prim_box("he_bounds", (-2.119, 6.0 - 1.983, -2.130), (1.767, 6.0 + 1.660, 2.870)), wire_white)
    wire(box, 0.025)
    kit.add_object(c["ref_he_thrown"], "he_thrown_body", prim_sphere("he_thrown_body", HE_BODY_D * THROWN_SCALE / 2, (0.0, 1.0 + proj_d, 0.0)), olive)
    kit.add_object(c["ref_player"], "player_hull", prim_box("player_hull", (-16, pile_lo[1] - 40, 0), (16, pile_lo[1] - 8, 72)), grey)
    kit.add_object(c["floor"], "floor", prim_box("floor", (-400, -400, -1.0), (400, 400, 0.0)), floor)

    area_lights(c["rig_small"], (0, 0, 0), 30.0, 9000.0)
    sun = bpy.data.lights.new("rig_large_sun", "SUN")
    sun.energy, sun.angle = 3.2, math.radians(5)
    so = bpy.data.objects.new("rig_large_sun", sun)
    so.rotation_euler = Vector((-0.55, 0.45, -0.7)).to_track_quat("-Z", "Y").to_euler()  # light travels down -Z
    c["rig_large"].objects.link(so)
    area_lights(c["rig_large"], (0, 0, 10), 240.0, 180000.0)

    cams = c["cameras"]
    rc = Vector(((held_lo + held_hi) / 2).tolist())
    pc = Vector(((pile_lo + pile_hi) / 2).tolist())
    k = float(max(pile_hi[0] - pile_lo[0], pile_hi[1] - pile_lo[1], pile_hi[2] * 2.0)) / 44.0  # a 44" pile frames at 1
    py = (proj_d + 1.0) / 2
    return [
        ("held", ["held", "rig_small"], camera(cams, "cam_held", rc + Vector((13.0, -10.0, 6.0)), rc, 85)),
        ("held_closeup", ["held", "rig_small"], camera(cams, "cam_held_close", rc + Vector((5.6, -4.3, 2.2)), rc + Vector((-0.2, 0.9, 0.7)), 85)),
        ("held_alignment", ["ghost", "ref_decoy", "rig_small"], camera(cams, "cam_align", (0.0, -30.0, 0.2), (0.0, 0.0, 0.2), ortho=10.0)),
        ("scale_he", ["held", "ref_he", "rig_small"], camera(cams, "cam_scale", (16.0, 3.0, 0.0), (0.0, 3.0, 0.0), ortho=13.0)),
        ("projectile", ["projectile", "ref_he_thrown", "rig_small"], camera(cams, "cam_proj", (18.0, py, 0.0), (0.0, py, 0.0), ortho=14.0)),
        ("pile", ["pile", "floor", "rig_large"], camera(cams, "cam_pile", pc + k * Vector((78.0, -62.0, 55.0)), pc, 50)),
        ("pile_high", ["pile", "floor", "rig_large"], camera(cams, "cam_pile_high", pc + k * Vector((30.0, -26.0, 112.0)), pc, 40)),
        ("pile_closeup", ["pile", "floor", "rig_large"], camera(cams, "cam_pile_close", pc + k * Vector((26.0, -20.0, 18.0)), pc + Vector((0, 0, 2.0)), 50)),
        ("pile_player", ["pile", "floor", "ref_player", "rig_large"], camera(cams, "cam_pile_player", (150.0, pile_lo[1] - 4.0, 50.0), (0.0, pile_lo[1] - 4.0, 30.0), 35)),
    ]


def render(shots, colls, render_dir, prefix, layers, only=None):
    sc = bpy.context.scene
    os.makedirs(render_dir, exist_ok=True)
    toggled = [k for k in colls if k != "cameras"]
    for name, visible, cam in shots:
        if only and name not in only:
            continue
        for k in toggled:
            colls[k].hide_render = k not in visible
        sc.camera = cam
        sc.render.filepath = os.path.join(render_dir, f"{prefix}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", sc.render.filepath)
    icon = os.path.join(render_dir, f"{prefix}_icon_x8.png")
    icon_preview(icon, layers)
    print("RENDERED", icon)


# ---------------------------------------------------------------- main

def main():
    A = kit.cli(__doc__, ("--only", "comma-separated preview shots to render, e.g. held,pile"))
    addon = lambda rel: os.path.join(A.addon_root, *rel.split("/"))
    colls = new_scene()
    pngs = make_textures(addon(MAT_REL))
    for name, rough in ROUGH.items():
        kit.write_vmat(addon(f"{MAT_REL}/{name}.vmat"), f"{MAT_REL}/{name}_color.png", rough, comment=COMMENTS[name])
    layers = icon_layers()
    write_svg(addon(ICON_REL), layers)
    mats = {k: kit.blender_material(k, pngs[k], rough=ROUGH[k]) for k in ROUGH}

    v, f, uv = egg_parts(HELD_L, 48, 34)
    held = kit.add_object(colls["held"], "easter_egg_held", kit.mesh_from("easter_egg_held", v + np.array(BODY_CENTRE), f, uv),
                          mats["easter_egg"])
    v, f, uv = egg_parts(PROJ_L, 40, 26)
    proj = kit.add_object(colls["projectile"], "easter_egg_projectile", kit.mesh_from("easter_egg_projectile", v, f, uv),
                          mats["easter_egg"])

    nest_me, dense = nest_mesh()
    nest = kit.add_object(colls["pile"], "easter_egg_nest", nest_me, mats["easter_egg_nest"])
    eggs = []
    for i, (c, frame, length, var) in enumerate(build_pile(nest_top(dense))):
        _, _, v_lo, v_hi = atlas_tile(var, len(DESIGNS), 2048)
        v, f, uv = egg_parts(length, 24, 14, v_lo, v_hi)
        me = kit.mesh_from(f"pile_egg_{i:02d}", v @ frame.T + c, f, uv)
        eggs.append(kit.add_object(colls["pile"], f"pile_egg_{i:02d}", me, mats["easter_egg_pile"]))
    pile = [nest] + eggs

    for ob in [held, proj] + pile:
        gate(ob)
    print("GATE ok: every part has positive signed volume and no non-manifold edges")

    out = lambda name: os.path.join(A.out, name)
    S = kit.write_smd
    tri_held = S(out("easter_egg_held.smd"), DECOY_BONES, 1, [(held, "easter_egg")])
    tri_proj = S(out("easter_egg_projectile.smd"), PROP_BONES, 0, [(proj, "easter_egg")])
    tri_pile = S(out("easter_egg_pile.smd"), PROP_BONES, 0,
                 [(nest, "easter_egg_nest")] + [(ob, "easter_egg_pile") for ob in eggs])
    H = kit.write_hull_dmx
    hv_held = H(out("easter_egg_held_hull.dmx"), "easter_egg_held_hull", kit.support_points([held], 40), "$" + DECOY_SURFACE)
    hv_proj = H(out("easter_egg_projectile_hull.dmx"), "easter_egg_projectile_hull", kit.support_points([proj], 28), "$fruit")
    hv_nest = H(out("easter_egg_pile_nest_hull.dmx"), "easter_egg_pile_nest_hull", kit.support_points([nest], 40), "$foliage")
    hv_eggs = H(out("easter_egg_pile_eggs_hull.dmx"), "easter_egg_pile_eggs_hull", kit.support_points(eggs, 56), "$fruit")

    h_lo, h_hi = kit.bounds([held])
    p_lo, p_hi = kit.bounds([proj])
    k_lo, k_hi = kit.bounds(pile)
    ao_r = 0.95 * HELD_W / 2
    half = max(0.0, 0.95 * HELD_L / 2 - ao_r)
    cz = (h_lo[2] + h_hi[2]) / 2
    r3 = lambda p: [round(float(c), 3) for c in p]
    ao = {"bonename": "weapon_offset", "radius": round(float(ao_r), 3), "point0": r3((0.0, 0.0, cz - half)),
          "point1": r3((0.0, 0.0, cz + half))}
    remap = lambda *names: [(n, f"{MAT_REL}/{n}.vmat") for n in names]
    raw = lambda name: A.out_rel + name
    kit.write_weapon_vmdl(addon(VMDL_HELD), remap("easter_egg"), raw("easter_egg_held.smd"), raw("easter_egg_held_hull.dmx"),
                          DECOY_SURFACE, DECOY_ATTACHMENTS, ("hudmodel", "dropped", "thrown"), DECOY_NMSKEL,
                          DECOY_HOLSTER, (h_lo, h_hi), DECOY_BONES, [("ao_proxy_capsule", ao)])
    write_prop_vmdl(addon(VMDL_PROJ), remap("easter_egg"), raw("easter_egg_projectile.smd"),
                    [("body", raw("easter_egg_projectile_hull.dmx"), "fruit")], (0.0, 0.0, round(float(p_hi[2]), 2)))
    write_prop_vmdl(addon(VMDL_PILE), remap("easter_egg_pile", "easter_egg_nest"), raw("easter_egg_pile.smd"),
                    [("nest", raw("easter_egg_pile_nest_hull.dmx"), "foliage"),
                     ("eggs", raw("easter_egg_pile_eggs_hull.dmx"), "fruit")])

    egg_tris = sum(len(ob.data.loop_triangles) for ob in eggs)
    fmt = kit.fmt
    print(f"STATS held tris={tri_held} verts={len(held.data.vertices)} hull_verts={hv_held}")
    print(f"STATS projectile tris={tri_proj} verts={len(proj.data.vertices)} hull_verts={hv_proj}")
    print(f"STATS pile tris={tri_pile} eggs={len(eggs)} egg_tris={egg_tris} nest_tris={tri_pile - egg_tris} "
          f"hull_verts nest={hv_nest} eggs={hv_eggs}")
    print(f"BOUNDS held model min={fmt(h_lo)} max={fmt(h_hi)} centre={fmt((h_lo + h_hi) / 2)} size={fmt(h_hi - h_lo)}")
    print(f"HITBOX weapon_offset-space mins=[{h_lo[0]:.3f}, {h_lo[1]:.3f}, {h_lo[2]:.3f}] maxs=[{h_hi[0]:.3f}, {h_hi[1]:.3f}, {h_hi[2]:.3f}]")
    print(f"AO capsule radius={ao_r:.3f} z={cz - half:.3f}..{cz + half:.3f}")
    print(f"BOUNDS projectile model min={fmt(p_lo)} max={fmt(p_hi)} size={fmt(p_hi - p_lo)}")
    print(f"BOUNDS pile model min={fmt(k_lo)} max={fmt(k_hi)} size={fmt(k_hi - k_lo)}")
    print(f"PILE footprint={k_hi[0] - k_lo[0]:.1f}x{k_hi[1] - k_lo[1]:.1f} height={k_hi[2]:.2f} "
          f"nest_rim_top={kit.bounds([nest])[1][2]:.2f} egg_count={len(eggs)}")
    print(f"SIZE held L={HELD_L:.3f} ({HELD_L / HE_BODY_D:.3f}x HE body {HE_BODY_D}) W={HELD_W:.3f} ({HELD_W / HELD_L:.2f} L) "
          f"projectile L={PROJ_L:.3f} pile egg L~{PILE_EGG_L:.2f}")

    shots = setup_preview(colls, [held], h_lo, h_hi, float(max(p_hi[0] - p_lo[0], p_hi[1] - p_lo[1])), k_lo, k_hi)
    kit.save_blend(out("easter_egg.blend"))
    if A.render:
        render(shots, colls, A.render, "easter_egg", layers, A.only.split(",") if A.only else None)


main()
