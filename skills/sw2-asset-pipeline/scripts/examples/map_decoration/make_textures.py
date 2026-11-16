"""Procedural textures for the Christmas tree decoration (build_christmas_tree.py).

Run with a system Python 3.10+ that has Pillow and numpy (Blender's Python lacks Pillow):
    python make_textures.py --addon-root <content/csgo_addons/<addon>>
Writes PNGs into <addon>/materials/christmas_tree/. Seeds are fixed, so reruns are stable.
"""
import argparse
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MAT_REL = "materials/christmas_tree"
OUT = None  # set by main()
SS = 2  # draw supersampled, downsample once for antialiasing

NEEDLES = {
    "old": (17, 44, 27),
    "mid": (31, 76, 44),
    "young": (52, 108, 60),
    "new": (84, 138, 70),
    "twig": (82, 60, 40),
    "bg": (26, 58, 36),
}


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c0, c1, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c0, c1))


def scale(c, f):
    return tuple(max(0, min(255, int(round(v * f)))) for v in c)


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path, optimize=True)
    print(f"wrote {name} {img.size[0]}x{img.size[1]} {img.mode}")


# ---------------------------------------------------------------- branch atlas

def walk(start, angle, length, bend, segments=8):
    pts = [start]
    x, y = start
    a = angle
    step = length / segments
    for _ in range(segments):
        x += math.cos(a) * step
        y += math.sin(a) * step
        pts.append((x, y))
        a += bend / segments
    return pts


def needles_along(rng, pts, spacing, length, spread, top_chance, g0, g1):
    """Needles both sides of a polyline: (x, y, angle, len, f along twig, g along branch)."""
    out = []
    seglens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seglens) or 1.0
    walked = 0.0
    for i, seg in enumerate(seglens):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        ang = math.atan2(y1 - y0, x1 - x0)
        n = max(1, int(seg / spacing))
        for k in range(n):
            t = (k + rng.random()) / n
            x, y = lerp(x0, x1, t), lerp(y0, y1, t)
            f = (walked + seg * t) / total
            g = lerp(g0, g1, f)
            shrink = 1.0 - 0.35 * f * f
            for side in (-1.0, 1.0):
                a = ang + side * math.radians(rng.uniform(*spread))
                out.append((x, y, a, rng.uniform(*length) * shrink, f, g))
            if rng.random() < top_chance:
                a = ang + math.radians(rng.uniform(-40, 40))
                out.append((x, y, a, rng.uniform(*length) * rng.uniform(0.25, 0.5), f, g))
        walked += seg
    return out


def needle_color(rng, pal, f, g):
    c = mix(pal["old"], pal["mid"], 0.45 * f + 0.65 * g)
    c = mix(c, pal["young"], max(0.0, f - 0.5) * 1.6 * rng.random())
    if f > 0.86 and rng.random() < 0.8:
        c = mix(c, pal["new"], (f - 0.86) / 0.14)
    return scale(c, rng.uniform(0.80, 1.16))


def fits(pts, cy, half, pad):
    return all(abs(y - cy) < half - pad for _, y in pts)


def draw_branch(seed, darken):
    """One spruce branch seen from above: base at x=0, tip at x=W."""
    rng = random.Random(seed)
    W, H = 2048 * SS, 1024 * SS
    pal = {k: scale(v, darken) for k, v in NEEDLES.items()}
    col = Image.new("RGBA", (W, H), pal["bg"] + (0,))
    hgt = Image.new("L", (W, H), 0)
    dc, dh = ImageDraw.Draw(col), ImageDraw.Draw(hgt)
    cy, half = H / 2, H / 2
    pad = 60 * SS  # keeps needles off the atlas seam
    needle_len = (26 * SS, 42 * SS)

    phase = rng.uniform(0, math.tau)
    stem = [(lerp(30 * SS, W - 36 * SS, i / 48),
             cy + math.sin(i / 48 * math.pi * 1.3 + phase) * 16 * SS) for i in range(49)]

    def stem_at(t):
        f = t * 48
        i = min(47, int(f))
        (x0, y0), (x1, y1) = stem[i], stem[i + 1]
        return (lerp(x0, x1, f - i), lerp(y0, y1, f - i))

    twigs = []  # (points, w0, w1, g)
    t = rng.uniform(0.03, 0.05)
    side = rng.choice((-1, 1))
    while t < 0.93:
        env = math.sin(math.pi * min(t, 0.97) ** 0.85) ** 0.75
        length = (0.2 + 0.8 * env) * 0.56 * H * rng.uniform(0.85, 1.0)
        ang = side * math.radians(rng.uniform(44, 58))
        bend = -side * math.radians(rng.uniform(8, 18))
        pts = walk(stem_at(t), ang, length, bend)
        while not fits(pts, cy, half, pad) and length > 20:
            length *= 0.9
            pts = walk(stem_at(t), ang, length, bend)
        twigs.append((pts, 8 * SS, 3 * SS, t))
        if length > 0.12 * H:
            for _ in range(rng.randint(2, 3) + int(length / (0.14 * H))):
                f = rng.uniform(0.2, 0.85)
                k = min(len(pts) - 2, int(f * (len(pts) - 1)))
                (x0, y0), (x1, y1) = pts[k], pts[k + 1]
                local = math.atan2(y1 - y0, x1 - x0)
                s = rng.choice((-1, 1))
                sub_len = length * rng.uniform(0.25, 0.45)
                sub_ang = local + s * math.radians(rng.uniform(35, 55))
                sub = walk(pts[k], sub_ang, sub_len, -s * math.radians(10), 5)
                while not fits(sub, cy, half, pad) and sub_len > 10:
                    sub_len *= 0.85
                    sub = walk(pts[k], sub_ang, sub_len, -s * math.radians(10), 5)
                twigs.append((sub, 4 * SS, 2 * SS, t))
        t += rng.uniform(0.022, 0.032)
        side = -side if rng.random() < 0.8 else side

    # woody parts first; needles cover most of them, as on a real spruce
    for i in range(len(stem) - 1):
        w = int(lerp(20 * SS, 7 * SS, i / 47))
        dc.line([stem[i], stem[i + 1]], fill=pal["twig"] + (255,), width=w)
        dh.line([stem[i], stem[i + 1]], fill=150, width=w)
    for pts, w0, w1, _ in twigs:
        for i in range(len(pts) - 1):
            w = max(1, int(lerp(w0, w1, i / max(1, len(pts) - 2))))
            dc.line([pts[i], pts[i + 1]], fill=pal["twig"] + (255,), width=w)
            dh.line([pts[i], pts[i + 1]], fill=150, width=w)

    needles = needles_along(rng, stem, 4 * SS, needle_len, (35, 80), 0.7, 0.0, 1.0)
    for pts, _, _, g in twigs:
        needles += needles_along(rng, pts, 5 * SS, needle_len, (35, 80), 0.7, g, min(1.0, g + 0.25))
    rng.shuffle(needles)
    for x, y, a, ln, f, g in needles:
        c = needle_color(rng, pal, f, g)
        xm, ym = x + math.cos(a) * ln * 0.5, y + math.sin(a) * ln * 0.5
        x1, y1 = x + math.cos(a) * ln, y + math.sin(a) * ln
        dc.line([(x, y), (xm, ym)], fill=scale(c, 0.78) + (255,), width=3 * SS)
        dc.line([(xm, ym), (x1, y1)], fill=c + (255,), width=5 * SS // 2)
        dh.line([(x, y), (x1, y1)], fill=255, width=5 * SS // 2)

    col = col.resize((W // SS, H // SS), Image.LANCZOS)
    hgt = hgt.resize((W // SS, H // SS), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8))
    return col, hgt, pal["bg"]


def bleed(rgba, bg):
    """Fill transparent texels with nearby needle colour so mips/bilinear don't fringe."""
    a = np.asarray(rgba, dtype=np.float32)
    alpha = a[..., 3:4] / 255.0
    rgb = a[..., :3]
    weighted = Image.fromarray(np.clip(rgb * alpha, 0, 255).astype(np.uint8), "RGB")
    wmask = Image.fromarray((alpha[..., 0] * 255).astype(np.uint8), "L")
    blur_rgb = np.asarray(weighted.filter(ImageFilter.GaussianBlur(10)), dtype=np.float32)
    blur_a = np.asarray(wmask.filter(ImageFilter.GaussianBlur(10)), dtype=np.float32)[..., None] / 255.0
    fill = np.where(blur_a > 1e-3, blur_rgb / np.maximum(blur_a, 1e-3), np.array(bg, np.float32))
    out_rgb = rgb * alpha + fill * (1.0 - alpha)
    out = np.concatenate([np.clip(out_rgb, 0, 255), a[..., 3:4]], axis=-1)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def normal_from_height(height, strength, mask=None):
    """OpenGL convention (green = +V)."""
    h = np.asarray(height, dtype=np.float32) / 255.0
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx * inv, ny * inv, nz * inv], axis=-1)
    if mask is not None:
        m = (np.asarray(mask, dtype=np.float32) / 255.0)[..., None]
        n = n * m + np.array([0, 0, 1], np.float32) * (1 - m)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return Image.fromarray(((n * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), "RGB")


def make_branch_atlas():
    outer, outer_h, bg_o = draw_branch(1225, 1.0)
    inner, inner_h, bg_i = draw_branch(2412, 0.62)
    outer, inner = bleed(outer, bg_o), bleed(inner, bg_i)

    color = Image.new("RGBA", (2048, 2048))
    color.paste(outer, (0, 0))
    color.paste(inner, (0, 1024))
    alpha = color.getchannel("A")
    trans = Image.merge("RGBA", (alpha, alpha, alpha, alpha))

    height = Image.new("L", (2048, 2048))
    height.paste(outer_h, (0, 0))
    height.paste(inner_h, (0, 1024))
    save(color, "branch_color.png")
    save(trans, "branch_trans.png")
    save(normal_from_height(height, 4.0, alpha), "branch_normal.png")


# ---------------------------------------------------------------- tileables

def wrap_line(draw, p0, p1, size, **kw):
    xs, ys = (p0[0], p1[0]), (p0[1], p1[1])
    pad = kw.get("width", 1)
    for dx in (-size, 0, size):
        if max(xs) + dx < -pad or min(xs) + dx > size + pad:
            continue
        for dy in (-size, 0, size):
            if max(ys) + dy < -pad or min(ys) + dy > size + pad:
                continue
            draw.line([(p0[0] + dx, p0[1] + dy), (p1[0] + dx, p1[1] + dy)], **kw)


def wrap_polygon(draw, pts, size, fill):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    for dx in (-size, 0, size):
        if max(xs) + dx < 0 or min(xs) + dx > size:
            continue
        for dy in (-size, 0, size):
            if max(ys) + dy < 0 or min(ys) + dy > size:
                continue
            draw.polygon([(x + dx, y + dy) for x, y in pts], fill=fill)


def tile_noise(rng, size, cells_x, cells_y):
    base = rng.random((cells_y, cells_x)).astype(np.float32)
    big = Image.fromarray((np.tile(base, (3, 3)) * 255).astype(np.uint8), "L")
    big = big.resize((size * 3, size * 3), Image.BICUBIC)
    return np.asarray(big, dtype=np.float32)[size:2 * size, size:2 * size] / 255.0


def make_core():
    """Dense, dark, opaque needles for the inner cone that stops the tree reading as see-through."""
    rng = random.Random(77)
    S = 1024 * SS
    img = Image.new("RGB", (S, S), (7, 18, 11))
    d = ImageDraw.Draw(img)
    old, mid = (12, 31, 19), (26, 58, 36)
    for _ in range(460):
        x, y = rng.uniform(0, S), rng.uniform(0, S)
        a = math.radians(rng.uniform(25, 155))  # image +y is down the tree: droop
        ln = rng.uniform(70, 170) * SS
        x1, y1 = x + math.cos(a) * ln, y + math.sin(a) * ln
        wrap_line(d, (x, y), (x1, y1), S, fill=(52, 40, 30), width=3 * SS)
        steps = int(ln / (5 * SS))
        for k in range(steps):
            t = k / max(1, steps)
            px, py = lerp(x, x1, t), lerp(y, y1, t)
            for side in (-1, 1):
                b = a + side * math.radians(rng.uniform(40, 80))
                nl = rng.uniform(15, 27) * SS
                c = scale(mix(old, mid, rng.random() * 0.8 + 0.2 * t), rng.uniform(0.8, 1.2))
                wrap_line(d, (px, py), (px + math.cos(b) * nl, py + math.sin(b) * nl), S, fill=c, width=2 * SS)
    img = img.resize((S // SS, S // SS), Image.LANCZOS)
    save(img, "core_color.png")


def make_bark():
    rng = np.random.default_rng(5)
    S = 512
    streak = tile_noise(rng, S, 22, 3)
    fine = tile_noise(rng, S, 96, 48)
    v = 0.65 * streak + 0.35 * fine
    dark, light = np.array([46, 32, 22], np.float32), np.array([104, 80, 58], np.float32)
    rgb = dark + (light - dark) * v[..., None]
    rgb *= np.where(streak < 0.28, 0.65, 1.0)[..., None]
    save(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB"), "bark_color.png")


def star_points(cx, cy, ro, ri, rot=-math.pi / 2):
    return [(cx + math.cos(rot + k * math.pi / 5) * (ro if k % 2 == 0 else ri),
             cy + math.sin(rot + k * math.pi / 5) * (ro if k % 2 == 0 else ri)) for k in range(10)]


def make_paper(name, base, accent, motif, seed):
    rng = np.random.default_rng(seed)
    S, step = 1024 * SS, 128 * SS
    img = Image.new("RGB", (S, S), base)
    d = ImageDraw.Draw(img)
    for row in range(S // step):
        for col in range(S // step):
            cx = col * step + (step / 2 if row % 2 else 0) + step / 4
            cy = row * step + step / 2
            if motif == "star":
                wrap_polygon(d, star_points(cx, cy, 24 * SS, 10 * SS), S, accent)
            else:
                for k in range(6):
                    a = k * math.pi / 3
                    tip = (cx + math.cos(a) * 26 * SS, cy + math.sin(a) * 26 * SS)
                    wrap_line(d, (cx, cy), tip, S, fill=accent, width=3 * SS)
                    for s in (-1, 1):
                        mx, my = cx + math.cos(a) * 15 * SS, cy + math.sin(a) * 15 * SS
                        b = a + s * math.radians(40)
                        wrap_line(d, (mx, my), (mx + math.cos(b) * 9 * SS, my + math.sin(b) * 9 * SS),
                                  S, fill=accent, width=2 * SS)
                ox, oy = cx + step / 2, cy
                r = 5 * SS
                wrap_polygon(d, [(ox + math.cos(t) * r, oy + math.sin(t) * r)
                                 for t in np.linspace(0, math.tau, 16, endpoint=False)], S, accent)
    img = img.resize((S // SS, S // SS), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float32)
    arr *= (1.0 + (rng.random(arr.shape[:2]) - 0.5) * 0.06)[..., None]
    arr *= (0.94 + 0.06 * tile_noise(rng, S // SS, 8, 8))[..., None]
    save(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB"), name)


SWATCHES = {
    "bauble_red_color.png": (196, 16, 22),
    "bauble_gold_color.png": (250, 192, 86),
    "light_red_color.png": (255, 46, 36),
    "star_frame_color.png": (214, 146, 92),
    "star_bulb_color.png": (255, 226, 168),
    "gift_ribbon_red_color.png": (168, 14, 26),
    "gift_ribbon_gold_color.png": (226, 170, 72),
}


def main():
    global OUT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--addon-root", required=True, help="content addon, e.g. <CS2>/content/csgo_addons/<addon>")
    OUT = os.path.join(p.parse_args().addon_root, *MAT_REL.split("/"))
    os.makedirs(OUT, exist_ok=True)
    make_branch_atlas()
    make_core()
    make_bark()
    make_paper("gift_paper_gold_color.png", (196, 142, 70), (222, 176, 102), "star", 11)
    make_paper("gift_paper_red_color.png", (172, 32, 48), (222, 118, 128), "snow", 12)
    for name, rgb in SWATCHES.items():
        save(Image.new("RGB", (16, 16), rgb), name)


if __name__ == "__main__":
    main()
