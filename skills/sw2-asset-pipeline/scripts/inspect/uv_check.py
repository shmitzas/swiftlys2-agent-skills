"""Read UVs back from a glTF export of a compiled model: the v at each draw call's highest and lowest vertex, and with
--tiles N, per atlas tile stacked in v, where its vertices sit and how height correlates with v. SMD and Blender
v = 1 is the top row of the PNG; glTF counts v from the top, so glTF v = 1 - SMD v.

    Source2Viewer-CLI -i <model>.vmdl_c -d --gltf_export_format gltf -o <scratch>/<name>.gltf
    python uv_check.py <scratch>/<name>.gltf [--tiles 8]
"""
import argparse
import os
import sys

import numpy as np

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
from measure_gltf import open_gltf, to_source  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gltf", help=".gltf from Source2Viewer-CLI -d --gltf_export_format gltf")
    ap.add_argument("--tiles", type=int, help="atlas tiles stacked in v; prints each tile's placement")
    a = ap.parse_args()
    g, acc = open_gltf(a.gltf)
    for mesh in g["meshes"]:
        for k, prim in enumerate(mesh["primitives"]):
            pos = to_source(acc(prim["attributes"]["POSITION"]).astype(float))
            indices = acc(prim["indices"]).ravel()
            idx = np.unique(indices)  # draw calls share one vertex buffer; keep this one's vertices
            src, uv = pos[idx], acc(prim["attributes"]["TEXCOORD_0"]).astype(float)[idx]
            top, bot = np.argmax(src[:, 2]), np.argmin(src[:, 2])
            print(f"UVCHECK {os.path.basename(a.gltf)} draw {k} tris={len(indices) // 3}: "
                  f"top z={src[top, 2]:.3f} gltf_v={uv[top, 1]:.4f} smd_v={1 - uv[top, 1]:.4f} | "
                  f"bottom z={src[bot, 2]:.3f} gltf_v={uv[bot, 1]:.4f} smd_v={1 - uv[bot, 1]:.4f}")
            for t in range(a.tiles or 0):
                sel = (uv[:, 1] >= t / a.tiles) & (uv[:, 1] < (t + 1) / a.tiles)
                if sel.sum() < 2:
                    continue
                p, v = src[sel], uv[sel, 1]
                lo, hi = p.min(0), p.max(0)
                corr = np.corrcoef(p[:, 2], v)[0, 1] if p[:, 2].std() > 0 and v.std() > 0 else float("nan")
                print(f"  tile {t} (counted from the PNG top): verts={int(sel.sum())} centre=({(lo[0] + hi[0]) / 2:.1f},"
                      f"{(lo[1] + hi[1]) / 2:.1f}) size={hi[0] - lo[0]:.1f}x{hi[1] - lo[1]:.1f}x{hi[2] - lo[2]:.1f} "
                      f"corr(z, gltf_v)={corr:+.2f}")


if __name__ == "__main__":
    main()
