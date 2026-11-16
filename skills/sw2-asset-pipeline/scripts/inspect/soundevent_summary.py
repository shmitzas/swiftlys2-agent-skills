"""Summarise stock soundevents: type, sound files (flagging any the live VPK lacks), position offset, child events.

    Source2Viewer-CLI -i <CS2>/game/csgo/pak01_dir.vpk -f soundevents/ -d -o <scratch>
    Source2Viewer-CLI -i <CS2>/game/csgo/pak01_dir.vpk -l > vpk_list.txt
    python soundevent_summary.py --events <scratch>/soundevents --list vpk_list.txt <file>.vsndevts::<event> [...]
Decompiled soundevents are Valve-derived: keep them out of git.
"""
import argparse
import os
import re


def read_text(path):
    raw = open(path, "rb").read()
    return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")  # Windows PowerShell's > writes UTF-16


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", required=True, help="folder of decompiled .vsndevts files")
    ap.add_argument("--list", required=True, help="output of Source2Viewer-CLI -i <vpk> -l")
    ap.add_argument("queries", nargs="+", metavar="FILE::EVENT", help="e.g. game_sounds_weapons.vsndevts::<event name>")
    a = ap.parse_args()
    present = {line.split(" CRC")[0].strip() for line in read_text(a.list).splitlines() if " CRC" in line}
    cache = {}

    def block(fname, name):
        """The event's top-level KV3 block, found by brace depth."""
        if fname not in cache:
            cache[fname] = read_text(os.path.join(a.events, fname)).splitlines()
        t = cache[fname]
        for i, line in enumerate(t):
            if line == f"\t{name} = ":
                depth, out = 0, []
                for j in range(i, len(t)):
                    out.append(t[j])
                    depth += t[j].count("{") - t[j].count("}")
                    if j > i and depth <= 0:
                        return "\n".join(out)
        return None

    for q in a.queries:
        fname, name = q.split("::")
        b = block(fname, name)
        if b is None:
            print(f"{name} NOT FOUND in {fname}")
            continue
        files = re.findall(r'"([^"]+\.vsnd)"', b)
        missing = [f for f in files if f + "_c" not in present]
        off = re.search(r"position_offset = \[([^\]]*)\]", b)
        kids = re.findall(r'soundevent_0\d = \s*\[\s*"([^"]+)"', b)
        typ = re.search(r'type = "([^"]+)"', b)
        print(f"{name:32s} {fname:30s} type={typ.group(1) if typ else '?'} files={len(files)} missing={len(missing)}"
              f"{' offset=[' + off.group(1).strip() + ']' if off else ''}{' children=' + ','.join(kids) if kids else ''}")
        for f in files[:4]:
            print(f"      {f}{'  <MISSING>' if f in missing else ''}")


if __name__ == "__main__":
    main()
