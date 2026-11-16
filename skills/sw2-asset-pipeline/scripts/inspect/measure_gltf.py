"""Bounds of a Source2Viewer-CLI glTF export per skinned bone, in Source inches and model space: how the stock decoy can
and the HE body were measured.

    Source2Viewer-CLI -i <model>.vmdl_c -d --gltf_export_format gltf -o <scratch>/<name>.gltf
    python measure_gltf.py <scratch>/<name>.gltf [--bones weapon,weapon_offset,...]
--bones names joint indices 0, 1, ...: the model's bones in -b DATA order, as model_facts.py prints them. Exports of
stock models are Valve-derived: keep them out of git.
"""
import argparse
import json
import os

import numpy as np

COMP = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def open_gltf(path):
    """(gltf json, accessor reader) for a .gltf with one external .bin buffer."""
    g = json.load(open(path))
    buf = open(os.path.join(os.path.dirname(path), g["buffers"][0]["uri"]), "rb").read()

    def acc(i):
        a = g["accessors"][i]
        bv = g["bufferViews"][a["bufferView"]]
        dt, n = np.dtype(COMP[a["componentType"]]), NCOMP[a["type"]]
        stride = bv.get("byteStride", dt.itemsize * n)
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        raw = np.frombuffer(buf, np.uint8, stride * (a["count"] - 1) + dt.itemsize * n, off)
        out = np.lib.stride_tricks.as_strided(raw, (a["count"], n * dt.itemsize), (stride, 1))
        return np.ascontiguousarray(out).view(dt).reshape(a["count"], n)

    return g, acc


def to_source(pos):
    return np.stack([pos[:, 2], pos[:, 0], pos[:, 1]], axis=1) / 0.0254  # glTF (x, y, z) = Source (y, z, x) * 0.0254


def report(path, names):
    g, acc = open_gltf(path)
    prim = g["meshes"][0]["primitives"][0]
    src = to_source(acc(prim["attributes"]["POSITION"]).astype(np.float64))
    idx = acc(prim["indices"]).ravel()
    print(f"== {os.path.basename(path)} verts={len(src)} tris={len(idx) // 3}")
    print("  all  min", np.round(src.min(0), 4), "max", np.round(src.max(0), 4))
    if "JOINTS_0" not in prim["attributes"]:
        return
    joints, weights = acc(prim["attributes"]["JOINTS_0"]), acc(prim["attributes"]["WEIGHTS_0"])
    main = joints[np.arange(len(joints)), np.argmax(weights, axis=1)]
    print("  max weight min:", float(weights.max(1).min()))
    for j in np.unique(main):
        p = src[main == j]
        nm = names[j] if j < len(names) else f"#{j}"
        c = (p.min(0) + p.max(0)) / 2
        print(f"  joint {j} ({nm}) n={len(p)} min={np.round(p.min(0), 4)} max={np.round(p.max(0), 4)} centre={np.round(c, 4)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gltf", help=".gltf from Source2Viewer-CLI -d --gltf_export_format gltf")
    ap.add_argument("--bones", default="", help="comma-separated names for joint indices 0, 1, ...")
    args = ap.parse_args()
    report(args.gltf, [b for b in args.bones.split(",") if b])
