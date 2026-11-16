"""Compare each compiled physics hull with the DMX it was built from: vertex counts, how far ResourceCompiler moved the
authored points (it re-fits hulls), how far the hull reaches past the render bounds and, with --floor, which compiled
vertices sank below the floor.

    Source2Viewer-CLI -i <model>.vmdl_c -a > model.txt
    python hull_report.py model.txt hull_a.dmx [hull_b.dmx ...] [--floor 0]
List the DMXs in the compiled hull order, which need not match the VMDL's PhysicsShapeList order. Compiled hull
vertices are in their parent bone's space, so a bone away from the model origin shows up as re-fit distance.
"""
import argparse
import os
import re
import struct

import numpy as np


def read_text(path):
    raw = open(path, "rb").read()
    return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")  # Windows PowerShell's > writes UTF-16


def block(text, name):
    m = re.search(rf'--- Data for block "{name}" ---\n(.*?)(?=\n--- Data for block "|\Z)', text, re.S)
    if not m:
        raise SystemExit(f"no {name} block: is this a Source2Viewer-CLI -a dump of a model?")
    return m.group(1)


def dmx_points(path):
    src = read_text(path).split('"position$0" "vector3_array"')[1].split("]")[0]
    return np.array([[float(c) for c in s.split()] for s in re.findall(r'"([-\d. ]+)"', src)])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dump", help="text from Source2Viewer-CLI -a")
    p.add_argument("dmx", nargs="+", help="hull DMX files (keyvalues2 text), in compiled hull order")
    p.add_argument("--floor", type=float, help="list compiled vertices more than 0.01 below this z")
    a = p.parse_args()
    text = read_text(a.dump).replace("\r\n", "\n")
    mdat, phys = block(text, "MDAT"), block(text, "PHYS")
    lo = np.array([float(c) for c in re.search(r"m_vMinBounds = \[ ([^\]]+) \]", mdat).group(1).split(",")])
    hi = np.array([float(c) for c in re.search(r"m_vMaxBounds = \[ ([^\]]+) \]", mdat).group(1).split(",")])
    hulls = re.findall(r"m_VertexPositions = \s*#\[(.*?)\]", phys, re.S)
    if len(hulls) != len(a.dmx):
        print(f"warning: the dump has {len(hulls)} hulls, {len(a.dmx)} DMX files given")
    for hexdata, dmx in zip(hulls, a.dmx):
        raw = bytes.fromhex("".join(hexdata.split()))
        comp = np.array([struct.unpack_from("<fff", raw, i) for i in range(0, len(raw) - len(raw) % 12, 12)])
        inp = dmx_points(dmx)
        out = np.maximum(comp.max(0) - hi, 0.0), np.maximum(lo - comp.min(0), 0.0)
        fid = [np.min(np.linalg.norm(inp - q, axis=1)) for q in comp]
        print(f"HULL {os.path.basename(dmx)} verts in={len(inp)} out={len(comp)} "
              f"beyond render bounds +{np.round(out[0], 3)} -{np.round(out[1], 3)} "
              f"re-fit max={max(fid):.3f} mean={np.mean(fid):.3f} (0 = kept as authored)")
        print(f"     input min={inp.min(0).round(3)} max={inp.max(0).round(3)}  output min={comp.min(0).round(3)} max={comp.max(0).round(3)}")
        if a.floor is not None:
            for q in comp[comp[:, 2] < a.floor - 0.01]:
                d = np.linalg.norm(inp - q, axis=1)
                j = int(np.argmin(d))
                print(f"     below floor {q.round(3)}  nearest input {inp[j].round(3)} at {d[j]:.3f}")


if __name__ == "__main__":
    main()
