"""Walk stock particles' references (child particles, materials, models) and flag any the live VPK lacks.

    Source2Viewer-CLI -i <CS2>/game/csgo/pak01_dir.vpk -l > vpk_list.txt
    python particle_refs.py --cli <Source2Viewer-CLI> --vpk <CS2>/game/csgo/pak01_dir.vpk --list vpk_list.txt
        --cache <scratch> particles/<path>.vpcf_c [...]
Particles are extracted into --cache once and reused: Valve-derived, keep them out of git.
"""
import argparse
import os
import re
import subprocess


def read_text(path):
    raw = open(path, "rb").read()
    return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")  # Windows PowerShell's > writes UTF-16


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cli", required=True, help="Source2Viewer-CLI executable (20.1 or newer for current builds)")
    ap.add_argument("--vpk", required=True, help="<CS2>/game/csgo/pak01_dir.vpk")
    ap.add_argument("--list", required=True, help="output of Source2Viewer-CLI -i <vpk> -l")
    ap.add_argument("--cache", required=True, help="scratch folder for extracted particles")
    ap.add_argument("particles", nargs="+", metavar="PARTICLE", help="VPK paths such as particles/<path>.vpcf_c")
    a = ap.parse_args()
    present = {line.split(" CRC")[0].strip() for line in read_text(a.list).splitlines() if " CRC" in line}

    def refs(path):
        local = os.path.join(a.cache, path.replace("/", os.sep))
        if not os.path.exists(local):
            os.makedirs(os.path.dirname(local), exist_ok=True)
            subprocess.run([a.cli, "-i", a.vpk, "-f", path, "-o", local], capture_output=True)
        r = subprocess.run([a.cli, "-i", local, "-b", "RERL"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return re.findall(r'm_pResourceName = "([^"]+)"', r.stdout)

    def walk(path, depth=0, seen=None):
        seen = seen if seen is not None else set()
        if path in seen:
            return
        seen.add(path)
        kinds = {}
        for ref in refs(path):
            kinds.setdefault(os.path.splitext(ref)[1], []).append((ref, (ref + "_c") in present))
        missing = [r for k in kinds.values() for r, ok in k if not ok]
        summary = ", ".join(f"{len(v)}{k}" for k, v in kinds.items())
        print(f"{'  ' * depth}{path}  [{summary}]{'  MISSING: ' + ', '.join(missing) if missing else ''}")
        for ref, ok in kinds.get(".vpcf", []):
            if ok:
                walk(ref + "_c", depth + 1, seen)
        if depth == 0:
            for k in (".vmdl", ".vmat"):
                for ref, ok in kinds.get(k, [])[:6]:
                    print(f"{'  ' * (depth + 1)}uses {ref}")

    for p in a.particles:
        walk(p)
        print()


if __name__ == "__main__":
    main()
