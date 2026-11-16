"""Pull the contract facts out of a Source2Viewer-CLI dump of a compiled model: bones and rest transforms, NmSkeleton
and resource references, game data, sequences, attachments, hitboxes, physics hulls, render bounds and draw calls.

    Source2Viewer-CLI -i <model>.vmdl_c -a > model.txt
    python model_facts.py model.txt [more.txt ...]
A stock model comes out of the VPK first:  -i <CS2>/game/csgo/pak01_dir.vpk -f <path>.vmdl_c -o <scratch>/<name>.vmdl_c
Current builds need the CLI 20.1 or newer. Stock dumps are Valve-derived: keep them out of git.
"""
import argparse
import re
import struct


def read_text(path):
    raw = open(path, "rb").read()
    return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")  # Windows PowerShell's > writes UTF-16


def section(text, block):
    m = re.search(rf'--- Data for block "{block}" ---\n(.*?)(?=\n--- Data for block "|\Z)', text, re.S)
    return m.group(1) if m else ""


def floats_hex(hexstr):
    b = bytes.fromhex(hexstr)
    return [struct.unpack_from("<fff", b, i) for i in range(0, len(b) - len(b) % 12, 12)]


def report(path):
    t = read_text(path).replace("\r\n", "\n")
    data, mdat, phys, rerl, aseq, red2 = (section(t, b) for b in ("DATA", "MDAT", "PHYS", "RERL", "ASEQ", "RED2"))
    print(f"==== {path}")
    print("RERL:", re.findall(r'm_pResourceName = "([^"]+)"', rerl))
    names = re.findall(r'"([^"]+)"', re.search(r"m_boneName = \s*\[(.*?)\]", data, re.S).group(1)) if "m_boneName" in data else []
    par = re.search(r"m_nParent = \s*\[(.*?)\]", data, re.S)
    pos = re.search(r"m_bonePosParent = \s*\[(.*?)\n\t\t\]", data, re.S)
    rot = re.search(r"m_boneRotParent = \s*\[(.*?)\n\t\t\]", data, re.S)
    if names:
        parents = [int(x) for x in re.findall(r"-?\d+", par.group(1))]
        poss = re.findall(r"\[ ([^\]]+) \]", pos.group(1))
        rots = re.findall(r"\[ ([^\]]+) \]", rot.group(1))
        for n, p, ps, rt in zip(names, parents, poss, rots):
            print(f"  bone {n:14s} parent={p:2d} pos=[{ps}] rot=[{rt}]")
    for key in ("m_remappingTable", "m_vecNmSkeletonRefs", "m_animGraph2Refs"):
        m = re.search(rf"{key} = \s*(\[.*?\])", data, re.S)
        if m:
            print(f"  {key}: {' '.join(m.group(1).split())}")
    kv = re.search(r'm_keyValueText = """(.*?)"""', data, re.S)
    if kv:
        body = kv.group(1)
        for blk in re.findall(r"\n\t(\w+) = ", body):
            print(f"  keyvalues block: {blk}")
        wm = re.search(r"weapon_metadata = \s*\{(.*?)\}", body, re.S)
        if wm:
            print("  weapon_metadata:", " ".join(wm.group(1).split()))
        ao = re.search(r"ao_proxy_capsule_list = \s*\[(.*?)\]\n", body, re.S)
        if ao:
            print("  ao_proxy_capsule_list:", " ".join(ao.group(1).split())[:200])
    print("  sequences:", re.findall(r'"([^"]+)"', re.search(r"m_localSequenceNameArray = \s*\[(.*?)\]", aseq, re.S).group(1)) if aseq else [])
    mins = re.findall(r"m_vMinBounds = \[ ([^\]]+) \]", mdat)
    maxs = re.findall(r"m_vMaxBounds = \[ ([^\]]+) \]", mdat)
    print(f"  render bounds (scene objects): min={mins[:1]} max={maxs[:1]}")
    vc = re.findall(r"m_nVertexCount = (\d+)", mdat)
    ic = re.findall(r"m_nIndexCount = (\d+)", mdat)
    mats = re.findall(r'm_material = resource:"([^"]+)"', mdat)
    print(f"  draw calls: verts={vc} indices={ic} (tris={[int(i) // 3 for i in ic]}) materials={mats}")
    for m in re.finditer(r'key = "([^"]+)"\s*value =\s*\{\s*m_name = "[^"]+"\s*m_influenceNames =\s*\[\s*"([^"]*)".*?m_vInfluenceOffsets =\s*\[\s*\[ ([^\]]+) \]', mdat, re.S):
        print(f"  attachment {m.group(1)} parent={m.group(2)!r} offset=[{m.group(3)}]")
    for m in re.finditer(r'm_name = "([^"]+)"\s*m_sSurfaceProperty = "([^"]+)"\s*m_sBoneName = "([^"]+)"\s*m_vMinBounds = \[ ([^\]]+) \]\s*m_vMaxBounds = \[ ([^\]]+) \]', mdat):
        print(f"  hitbox {m.group(1)} surf={m.group(2)} bone={m.group(3)} min=[{m.group(4)}] max=[{m.group(5)}]")
    print("  PHYS bones:", re.findall(r'"([^"]+)"', re.search(r"m_boneNames = \s*\[(.*?)\]", phys, re.S).group(1)) if "m_boneNames" in phys else None)
    print(f"  PHYS parts={len(re.findall(r'm_flMass = ', phys))} hulls={len(re.findall(r'm_Hull = ', phys))} "
          f"spheres/capsules/meshes empty={all(x in phys for x in ('m_spheres = [  ]', 'm_capsules = [  ]'))} mass={re.findall(r'm_flMass = ([\d.]+)', phys)}")
    hb = re.findall(r"m_Bounds = \s*\{\s*m_vMinBounds = \[ ([^\]]+) \]\s*m_vMaxBounds = \[ ([^\]]+) \]", phys)
    print(f"  PHYS hull bounds: {hb}")
    print(f"  PHYS surfacePropertyHashes: {re.findall(r'm_surfacePropertyHashes = \[ ([^\]]+) \]', phys)}  volume={re.findall(r'm_flVolume = ([\d.]+)', phys)}")
    for k, hexdata in enumerate(re.findall(r"m_VertexPositions = \s*#\[(.*?)\]", phys, re.S)):
        pts = floats_hex("".join(hexdata.split()))
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        print(f"  PHYS hull[{k}] verts={len(pts)} decoded min={[round(x, 3) for x in lo]} max={[round(x, 3) for x in hi]}")
    sud = re.search(r"m_SearchableUserData = \s*\{(.*?)\}", red2, re.S)
    if sud:
        keep = ("physics_shape_count", "physics_shape_hull_count", "model_bone_count", "model_lod0_triangle_count",
                "model_bone_weight_count", "model_nmskeletonref_count", "compile_warnings")
        print("  RED2:", {k: v for k, v in re.findall(r"(\w+) = (\S+)", sud.group(1)) if k in keep})
    print("  surface props:", re.findall(r"surface_prop = \s*\{(.*?)\}", red2, re.S)[0].split() if "surface_prop = " in red2 else None)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dumps", nargs="+", metavar="DUMP", help="text from Source2Viewer-CLI -a")
    for dump in p.parse_args().dumps:
        report(dump)
